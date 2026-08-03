from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import html
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from evolex.repositories.canonical import CanonicalGraphStore
from evolex.repositories.schema_store import SchemaCandidateStore


@dataclass(frozen=True)
class DashboardBundle:
    """Paths produced by a zero-service knowledge-graph HTML export."""

    output_dir: Path
    index_path: Path
    global_path: Path
    document_paths: dict[str, Path]


def build_dashboard(
    *,
    output_path: Path,
    canonical_dir: Path | None = None,
    registry_dir: Path | None = None,
    schema_dir: Path | None = None,
    document_id: str | None = None,
    run_id: str | None = None,
) -> Path:
    """Build one self-contained HTML graph without external assets.

    With ``document_id=None`` the page contains the active aggregate canonical
    graph.  A document-scoped page contains only entities grounded in that
    document and relations supported by its evidence (plus an explicitly
    labelled version-contribution fallback for legacy patches).
    """
    payload = _collect_dashboard_payload(
        canonical_dir=canonical_dir,
        registry_dir=registry_dir,
        schema_dir=schema_dir,
        document_id=document_id,
        run_id=run_id,
    )
    return _write_dashboard(output_path, payload)


def _collect_dashboard_payload(
    *,
    canonical_dir: Path | None,
    registry_dir: Path | None,
    schema_dir: Path | None,
    document_id: str | None,
    run_id: str | None,
) -> dict[str, Any]:
    with CanonicalGraphStore(canonical_dir) as store:
        if document_id is None:
            snapshot = store.snapshot()
            history = store.history(limit=100)
            document_ids = store.list_source_document_ids()
        else:
            snapshot = store.snapshot_for_document(document_id, run_id=run_id)
            history = store.history_for_document(
                document_id,
                run_id=run_id,
                limit=100,
            )
            document_ids = [document_id]
    selected_run_id = run_id or (
        str(history[0].get("run_id", "")) if history else None
    )
    governance = _load_governance(registry_dir, run_id=selected_run_id)
    schema = SchemaCandidateStore(schema_dir).get_active_schema()
    scope = {
        "kind": "document" if document_id is not None else "global",
        "document_id": document_id,
        "selected_run_id": selected_run_id,
        "run_ids": sorted(
            {
                str(item.get("run_id", ""))
                for item in history
                if str(item.get("run_id", ""))
            }
        ),
        "source_version_ids": [
            str(item.get("version_id", ""))
            for item in history
            if str(item.get("version_id", ""))
        ],
        "global_active_version_id": (
            snapshot.get("global_version_id") or snapshot.get("version_id")
        ),
        "provenance_mode": snapshot.get(
            "provenance_mode",
            "aggregate_active_canonical_graph",
        ),
    }
    return {
        "snapshot": snapshot,
        "history": history,
        "governance": governance,
        "schema": schema,
        "scope": scope,
        "document_ids": document_ids,
    }


def _write_dashboard(output_path: Path, payload: dict[str, Any]) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(payload, ensure_ascii=False)
        .replace("</", "<\\/")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
    output_path.write_text(_html(encoded), encoding="utf-8")
    return output_path


def build_dashboard_bundle(
    *,
    output_dir: Path,
    canonical_dir: Path | None = None,
    registry_dir: Path | None = None,
    schema_dir: Path | None = None,
) -> DashboardBundle:
    """Export a global graph, one graph per document, and a static index."""
    output_dir.mkdir(parents=True, exist_ok=True)
    documents_dir = output_dir / "documents"
    documents_dir.mkdir(parents=True, exist_ok=True)
    global_payload = _collect_dashboard_payload(
        canonical_dir=canonical_dir,
        registry_dir=registry_dir,
        schema_dir=schema_dir,
        document_id=None,
        run_id=None,
    )
    document_ids = list(global_payload["document_ids"])
    global_path = _write_dashboard(
        output_dir / "evolex-global-kg.html",
        global_payload,
    )
    document_paths: dict[str, Path] = {}
    document_counts: dict[str, dict[str, int]] = {}
    for document_id in document_ids:
        path = documents_dir / _safe_document_filename(document_id)
        payload = _collect_dashboard_payload(
            canonical_dir=canonical_dir,
            registry_dir=registry_dir,
            schema_dir=schema_dir,
            document_id=document_id,
            run_id=None,
        )
        snapshot = payload["snapshot"]
        document_counts[document_id] = {
            "entities": len(snapshot["entities"]),
            "relations": len(snapshot["relations"]),
        }
        document_paths[document_id] = _write_dashboard(
            path,
            payload,
        )
    index_path = output_dir / "index.html"
    index_path.write_text(
        _index_html(
            global_path=global_path,
            document_paths=document_paths,
            document_counts=document_counts,
        ),
        encoding="utf-8",
    )
    return DashboardBundle(
        output_dir=output_dir,
        index_path=index_path,
        global_path=global_path,
        document_paths=document_paths,
    )


def _safe_document_filename(document_id: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", document_id).strip(".-")
    base = (normalized or "document")[:64]
    suffix = sha256(document_id.encode("utf-8")).hexdigest()[:10]
    return f"evolex-doc-{base}-{suffix}.html"


def _load_governance(
    registry_dir: Path | None,
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    directory = registry_dir or Path("data/registry")
    if not directory.exists():
        return {}
    candidates = sorted(directory.glob("*_registry.sqlite"))
    if run_id:
        path = next(
            (
                candidate
                for candidate in candidates
                if candidate.name.removesuffix("_registry.sqlite") == run_id
            ),
            None,
        )
        if path is None:
            return {
                "selected_run_id": run_id,
                "binding_status": "exact_registry_missing",
            }
    else:
        candidates = sorted(
            candidates,
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            return {}
        path = candidates[0]
    conn = sqlite3.connect(str(path))
    try:
        trace = _json_rows(
            conn,
            "SELECT trace_json FROM agent_trace ORDER BY step_index, id",
        )
        merges = _json_rows(
            conn,
            "SELECT decision_json FROM merge_decisions ORDER BY id",
        )
        objects = _candidate_objects(conn)
        policy = _json_rows(
            conn,
            "SELECT decision_json FROM policy_decisions ORDER BY id",
        )
        registry_run_ids = _registry_run_ids(conn)
        binding_status = (
            "exact_run_id"
            if run_id and registry_run_ids == {run_id}
            else "registry_empty_or_unverified"
            if run_id
            else "independent_latest_by_mtime"
        )
        return {
            "registry_path": str(path),
            "selected_run_id": run_id,
            "registry_run_ids": sorted(registry_run_ids),
            "binding_status": binding_status,
            "agent_trace": trace,
            "merge_decisions": merges,
            "policy_decisions": policy,
            **objects,
        }
    except sqlite3.OperationalError:
        return {
            "registry_path": str(path),
            "selected_run_id": run_id,
            "binding_status": "registry_unreadable_or_legacy_schema",
        }
    finally:
        conn.close()


def _registry_run_ids(conn: sqlite3.Connection) -> set[str]:
    table_rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    tables = {str(row[0]) for row in table_rows}
    run_ids: set[str] = set()
    for table in (
        "candidates",
        "policy_decisions",
        "merge_decisions",
        "agent_trace",
        "entity_decisions",
        "quarantine_records",
        "audit_events",
    ):
        if table not in tables:
            continue
        columns = {
            str(row[1])
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if "run_id" not in columns:
            continue
        rows = conn.execute(f"SELECT DISTINCT run_id FROM {table}").fetchall()
        run_ids.update(str(row[0]) for row in rows if row[0])
    return run_ids


def _json_rows(conn: sqlite3.Connection, query: str) -> list[dict]:
    rows = conn.execute(query).fetchall()
    result = []
    for row in rows:
        try:
            value = json.loads(row[0])
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            result.append(value)
    return result


def _candidate_objects(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT object_type, object_json FROM candidates
        WHERE object_type IN
            ('graph_patch', 'shadow_evaluation', 'evolution_decision',
             'evolution_commit')
        ORDER BY id
        """
    ).fetchall()
    result: dict[str, Any] = {}
    for object_type, value in rows:
        try:
            result[str(object_type)] = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            continue
    return result


def _index_html(
    *,
    global_path: Path,
    document_paths: dict[str, Path],
    document_counts: dict[str, dict[str, int]],
) -> str:
    base_dir = global_path.parent
    rows = []
    for document_id, path in sorted(document_paths.items()):
        counts = document_counts.get(document_id, {})
        relative_path = path.relative_to(base_dir).as_posix()
        rows.append(
            "<li><a href=\"{}\"><span>{}</span>"
            "<small>{} entities · {} relations</small></a></li>".format(
                html.escape(relative_path, quote=True),
                html.escape(document_id),
                int(counts.get("entities", 0)),
                int(counts.get("relations", 0)),
            )
        )
    document_list = "".join(rows) or "<li class=\"empty\">暂无源文档。</li>"
    global_relative = global_path.relative_to(base_dir).as_posix()
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>EvoLex KG 静态可视化索引</title>
  <style>
    :root{{--ink:#17202a;--muted:#667085;--line:#d7dde5;--blue:#234c9f;}}
    *{{box-sizing:border-box}}
    body{{margin:0;background:#fff;color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}}
    main{{max-width:980px;margin:0 auto;padding:46px 28px 72px}}
    h1{{font-size:28px;margin:0 0 8px}} p{{color:var(--muted);margin:0 0 30px}}
    h2{{font-size:17px;margin:34px 0 12px;padding-bottom:8px;border-bottom:1px solid var(--line)}}
    a{{color:inherit;text-decoration:none}}
    .global{{display:block;border:1px solid var(--blue);padding:18px 20px;color:var(--blue);font-weight:700}}
    ul{{list-style:none;padding:0;margin:0;border-top:1px solid var(--line)}}
    li a{{display:flex;justify-content:space-between;gap:20px;padding:13px 4px;border-bottom:1px solid var(--line)}}
    li a:hover{{color:var(--blue)}} small{{color:var(--muted)}} .empty{{padding:14px 4px;color:var(--muted)}}
  </style>
</head>
<body><main>
  <h1>EvoLex Knowledge Graph</h1>
  <p>无需前端或后端服务。下列每个页面都把数据、样式和交互脚本内嵌在单一HTML中。</p>
  <a class="global" href="{html.escape(global_relative, quote=True)}">打开跨文档总知识图谱</a>
  <h2>单文档知识图谱（{len(document_paths)}）</h2>
  <ul>{document_list}</ul>
</main></body></html>"""


def _html(payload_json: str) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>EvoLex Knowledge Graph Evolution Control Plane</title>
  <style>
    :root {{
      --ink:#17202a; --muted:#667085; --line:#d7dde5; --paper:#fff;
      --card:#fff; --blue:#234c9f; --cyan:#287a91; --green:#287a55;
      --amber:#a86c16; --red:#b53e3e; --violet:#63528e;
    }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); background:var(--paper);
      font:14px/1.45 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif; }}
    header {{ padding:22px 28px; color:var(--ink); background:#fff;
      border-bottom:2px solid var(--blue); }}
    header h1 {{ margin:0 0 5px; font-size:24px; letter-spacing:.2px; }}
    header p {{ margin:0; color:var(--muted); }}
    .scope-line {{ display:flex; align-items:center; gap:9px; flex-wrap:wrap; }}
    .scope-badge {{ display:inline-block; padding:2px 8px; border:1px solid var(--blue);
      color:var(--blue); font-size:11px; font-weight:700; letter-spacing:.4px; }}
    main {{ padding:20px; max-width:1600px; margin:auto; }}
    .metrics {{ display:grid; grid-template-columns:repeat(6,minmax(130px,1fr)); gap:12px; }}
    .metric,.card {{ background:var(--card); border:1px solid var(--line); border-radius:3px; }}
    .metric {{ padding:14px 16px; }}
    .metric .n {{ font-size:25px; font-weight:760; color:var(--blue); }}
    .metric .l {{ color:var(--muted); margin-top:2px; }}
    .grid {{ display:grid; grid-template-columns:minmax(620px,1.65fr) minmax(350px,.85fr);
      gap:14px; margin-top:14px; }}
    .card {{ overflow:hidden; }}
    .card h2 {{ font-size:15px; margin:0; padding:13px 16px; border-bottom:1px solid var(--line); }}
    .toolbar {{ padding:9px 14px; border-bottom:1px solid var(--line);
      display:flex; align-items:center; gap:9px; color:var(--muted); flex-wrap:wrap; }}
    select,input,button {{ border:1px solid var(--line); border-radius:2px;
      padding:6px 8px; background:white; color:var(--ink); font:inherit; }}
    input {{ min-width:190px; }} button {{ cursor:pointer; }} button:hover {{ border-color:var(--blue); }}
    #graph {{ width:100%; height:620px; background:#fff; touch-action:none; cursor:grab; }}
    #graph.dragging {{ cursor:grabbing; }}
    .edge {{ stroke:#aab7ca; stroke-width:1.4; opacity:.78; cursor:pointer; }}
    .edge:hover {{ stroke:var(--blue); stroke-width:2.5; }}
    .node circle {{ stroke:#fff; stroke-width:3; cursor:pointer; }}
    .node text {{ font-size:11px; fill:var(--ink); pointer-events:none; text-anchor:middle;
      paint-order:stroke; stroke:#fff; stroke-width:3px; stroke-linejoin:round; }}
    .details {{ padding:14px 16px; min-height:185px; white-space:pre-wrap; overflow:auto; max-height:340px; }}
    .badge {{ display:inline-block; padding:2px 7px; border-radius:2px; color:white;
      font-size:11px; margin-right:5px; }}
    .ok {{ background:var(--green); }} .hold {{ background:var(--amber); }}
    .fail {{ background:var(--red); }} .info {{ background:var(--blue); }}
    .timeline,.trace {{ max-height:360px; overflow:auto; padding:10px 14px 14px; }}
    .event {{ border-left:3px solid var(--blue); padding:8px 10px; margin:7px 0; background:#f8faff; }}
    .event small,.subtle {{ color:var(--muted); }}
    .trace-row {{ display:grid; grid-template-columns:34px 1fr 65px 65px;
      gap:8px; padding:8px 2px; border-bottom:1px solid #edf1f6; align-items:center; }}
    .step {{ width:26px; height:26px; display:grid; place-items:center; border-radius:2px;
      background:#e8edff; color:var(--blue); font-weight:700; }}
    .mono {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12px; }}
    .wide {{ grid-column:1/-1; }}
    .query {{ display:grid; grid-template-columns:22px 1fr auto; gap:7px;
      padding:7px 0; border-bottom:1px solid #edf1f6; }}
    .certificate-grid {{ display:grid; grid-template-columns:repeat(3,minmax(220px,1fr));
      gap:10px; padding:14px 16px; }}
    .certificate-kv {{ padding:10px 12px; border:1px solid #e4eaf2;
      border-radius:3px; background:#fbfcff; min-width:0; }}
    .certificate-kv .key {{ display:block; color:var(--muted); font-size:12px;
      margin-bottom:5px; }}
    .certificate-kv .value {{ display:block; overflow-wrap:anywhere; }}
    .certificate-note {{ margin:0; padding:0 16px 14px; color:var(--muted); }}
    @media(max-width:980px) {{
      .metrics {{ grid-template-columns:repeat(2,1fr); }}
      .grid {{ grid-template-columns:1fr; }}
      .certificate-grid {{ grid-template-columns:1fr; }}
      #graph {{ height:520px; }}
    }}
  </style>
</head>
<body>
<header>
  <h1 id="pageTitle">EvoLex · Knowledge Graph Evolution Control Plane</h1>
  <div class="scope-line"><span class="scope-badge" id="scopeBadge">GLOBAL</span>
    <p id="scopeSummary">联合抽取、证据契约、双层规范化、影子验证与跨版本审计</p></div>
</header>
<main>
  <section class="metrics" id="metrics"></section>
  <section class="grid">
    <article class="card">
      <h2>Canonical Knowledge Graph</h2>
      <div class="toolbar">
        <label>关系 <select id="predicateFilter"><option value="">全部</option></select></label>
        <label>来源 <select id="sourceFilter"><option value="">全部文档</option></select></label>
        <label>实体 <input id="entitySearch" type="search" placeholder="搜索名称、类型或别名"></label>
        <button id="resetView" type="button">复位视图</button>
        <span id="graphHint">滚轮缩放，拖动平移，点击节点或边查看证据</span>
      </div>
      <svg id="graph" viewBox="0 0 900 560" role="img" aria-label="knowledge graph"></svg>
    </article>
    <aside>
      <article class="card">
        <h2>Evidence & Identity Details</h2>
        <div class="details" id="details">选择一个节点或关系。</div>
      </article>
      <article class="card" style="margin-top:14px">
        <h2>Evolution Versions</h2>
        <div class="timeline" id="timeline"></div>
      </article>
    </aside>
    <article class="card">
      <h2>Agent Decision Trace</h2>
      <div class="trace" id="trace"></div>
    </article>
    <article class="card">
      <h2>Impact-scoped Shadow Gates</h2>
      <div class="trace" id="queries"></div>
    </article>
    <article class="card wide">
      <h2>因果验证凭证与提交清单</h2>
      <div class="certificate-grid" id="certificate"></div>
      <p class="certificate-note">若canonical版本含run_id，则只读取同run_id的registry；缺失或核对失败时显示未绑定，不回退到其他文档的最新文件。N/A表示字段不存在，各来源标签保持独立。本视图不推断额外的 run_id–version_id 严格关联。</p>
    </article>
    <article class="card wide">
      <h2>Patch / Merge / Schema Audit</h2>
      <div class="details mono" id="audit"></div>
    </article>
  </section>
</main>
<script>
const DATA={payload_json};
const S=DATA.snapshot||{{entities:[],relations:[],relation_evidence:[],entity_mentions:[]}};
const G=DATA.governance||{{}};
const SCOPE=DATA.scope||{{kind:"global"}};
const M=S.entity_mentions||[];
const EV=S.relation_evidence||[];
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}}[c]));
const pct=n=>`${{Math.round(Number(n||0)*100)}}%`;
let graphFilters={{predicate:"",source:"",query:""}};
let baseView={{x:0,y:0,w:900,h:560}};
let graphView={{...baseView}};
let dragState=null;
const MAX_VISIBLE_ENTITIES=1200;
const MAX_VISIBLE_RELATIONS=1800;

function renderScope(){{
  const documentScope=SCOPE.kind==="document";
  document.querySelector("#scopeBadge").textContent=documentScope?"DOCUMENT":"GLOBAL";
  document.querySelector("#pageTitle").textContent=documentScope
    ? "EvoLex · 单文档 Knowledge Graph Evolution Control Plane"
    : "EvoLex · 总 Knowledge Graph Evolution Control Plane";
  document.querySelector("#scopeSummary").textContent=documentScope
    ? `内容快照 ${{SCOPE.document_id||"N/A"}} · ${{S.entities.length}} entities · ${{S.relations.length}} relations · provenance ${{SCOPE.provenance_mode||"N/A"}}`
    : `${{(DATA.document_ids||[]).length}} 个内容快照的 active canonical 总图；可按来源筛选`;
}}

function renderMetrics(){{
  const shadow=G.shadow_evaluation||{{}};
  const decision=G.evolution_decision||{{}};
  const values=[
    [S.entities.length,"Canonical entities"],
    [S.relations.length,"Canonical relations"],
    [EV.length,"Evidence anchors"],
    [(DATA.document_ids||[]).length,"Source documents"],
    [(DATA.history||[]).length,"Graph versions"],
    [Object.keys(decision).length?(decision.accepted?"ACCEPT":"HOLD"):"N/A","Latest evolution"]
  ];
  document.querySelector("#metrics").innerHTML=values.map(([n,l])=>
    `<div class="metric"><div class="n">${{esc(n)}}</div><div class="l">${{esc(l)}}</div></div>`).join("");
}}

const colors=["#234c9f","#287a91","#287a55","#a86c16","#63528e","#b53e3e","#56738f"];
function relationHasSource(relation,source){{
  if(!source) return true;
  return EV.some(item=>item.canonical_relation_id===relation.canonical_relation_id&&item.document_id===source);
}}
function entityMatches(entity,query){{
  if(!query) return true;
  const value=[entity.canonical_text,entity.entity_type,...(entity.aliases||[])].join(" ").toLowerCase();
  return value.includes(query.toLowerCase());
}}
function applyGraphView(){{
  document.querySelector("#graph").setAttribute(
    "viewBox",`${{graphView.x}} ${{graphView.y}} ${{graphView.w}} ${{graphView.h}}`
  );
}}
function resetGraphView(){{ graphView={{...baseView}}; applyGraphView(); }}

function renderGraph(){{
  const svg=document.querySelector("#graph");
  let relations=S.relations.filter(r=>
    (!graphFilters.predicate||r.predicate===graphFilters.predicate)&&relationHasSource(r,graphFilters.source)
  );
  let allowedEntityIds=new Set(S.entities.map(e=>e.canonical_id));
  if(graphFilters.source){{
    const mentionedIds=M.filter(item=>item.document_id===graphFilters.source).map(item=>item.canonical_id);
    allowedEntityIds=new Set([...mentionedIds,...relations.flatMap(r=>[r.subject_id,r.object_id])]);
  }}
  let entityPool=S.entities.filter(e=>allowedEntityIds.has(e.canonical_id));
  if(graphFilters.predicate){{
    const endpointIds=new Set(relations.flatMap(r=>[r.subject_id,r.object_id]));
    entityPool=entityPool.filter(e=>endpointIds.has(e.canonical_id));
  }}
  if(graphFilters.query){{
    const matches=new Set(entityPool.filter(e=>entityMatches(e,graphFilters.query)).map(e=>e.canonical_id));
    relations=relations.filter(r=>matches.has(r.subject_id)||matches.has(r.object_id));
    const neighborIds=new Set([...matches,...relations.flatMap(r=>[r.subject_id,r.object_id])]);
    entityPool=entityPool.filter(e=>neighborIds.has(e.canonical_id));
  }}
  const filteredRelationCount=relations.length;
  const filteredEntityCount=entityPool.length;
  relations=[...relations]
    .sort((a,b)=>Number(b.confidence||0)-Number(a.confidence||0)||String(a.canonical_relation_id).localeCompare(String(b.canonical_relation_id)))
    .slice(0,MAX_VISIBLE_RELATIONS);
  const degree={{}};
  relations.forEach(r=>{{degree[r.subject_id]=(degree[r.subject_id]||0)+1;degree[r.object_id]=(degree[r.object_id]||0)+1;}});
  const entities=[...entityPool]
    .sort((a,b)=>(degree[b.canonical_id]||0)-(degree[a.canonical_id]||0)||Number(b.confidence||0)-Number(a.confidence||0)||String(a.canonical_id).localeCompare(String(b.canonical_id)))
    .slice(0,MAX_VISIBLE_ENTITIES);
  const visibleEntityIds=new Set(entities.map(e=>e.canonical_id));
  relations=relations.filter(r=>visibleEntityIds.has(r.subject_id)&&visibleEntityIds.has(r.object_id));
  const maxRadius=entities.length>1?78*Math.sqrt(entities.length-1):0;
  const W=Math.max(900,Math.ceil(900+maxRadius*2));
  const H=Math.max(560,Math.ceil(560+maxRadius*1.36));
  const cx=W/2,cy=H/2;
  const pos={{}};
  entities.forEach((e,i)=>{{
    const angle=i*2.399963229728653;
    const radius=78*Math.sqrt(i);
    pos[e.canonical_id]={{x:cx+Math.cos(angle)*radius,y:cy+Math.sin(angle)*radius*.68}};
  }});
  const defs=`<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3"
    orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#aab7ca"/></marker></defs>`;
  const showEdgeLabels=relations.length<=120;
  const edges=relations.filter(r=>pos[r.subject_id]&&pos[r.object_id]).map(r=>{{
    const a=pos[r.subject_id],b=pos[r.object_id];
    return `<g data-rid="${{esc(r.canonical_relation_id)}}"><line class="edge"
      x1="${{a.x}}" y1="${{a.y}}" x2="${{b.x}}" y2="${{b.y}}" marker-end="url(#arrow)"/>
      ${{showEdgeLabels?`<text x="${{(a.x+b.x)/2}}" y="${{(a.y+b.y)/2-5}}" text-anchor="middle" font-size="10" fill="#667085">${{esc(r.predicate)}}</text>`:""}}</g>`;
  }}).join("");
  const types=[...new Set(entities.map(e=>e.entity_type))];
  const nodes=entities.map((e,i)=>{{
    const p=pos[e.canonical_id],color=colors[Math.max(0,types.indexOf(e.entity_type))%colors.length];
    const label=e.canonical_text.length>21?e.canonical_text.slice(0,19)+"…":e.canonical_text;
    return `<g class="node" data-eid="${{esc(e.canonical_id)}}" transform="translate(${{p.x}},${{p.y}})">
      <circle r="${{18+Math.min(8,Number(e.confidence||0)*8)}}" fill="${{color}}"/>
      <text y="38">${{esc(label)}}</text></g>`;
  }}).join("");
  const empty=entities.length?"":`<text x="${{W/2}}" y="${{H/2}}" text-anchor="middle" fill="#667085">当前筛选条件下没有知识对象</text>`;
  svg.innerHTML=defs+edges+nodes+empty;
  baseView={{x:0,y:0,w:W,h:H}}; resetGraphView();
  svg.querySelectorAll("[data-eid]").forEach(el=>el.onclick=()=>showEntity(el.dataset.eid));
  svg.querySelectorAll("[data-rid]").forEach(el=>el.onclick=()=>showRelation(el.dataset.rid));
  const limited=filteredEntityCount>entities.length||filteredRelationCount>relations.length;
  document.querySelector("#graphHint").textContent=limited
    ? `显示 ${{entities.length}} / ${{filteredEntityCount}} nodes · ${{relations.length}} / ${{filteredRelationCount}} edges；数据均已内嵌，请筛选后查看完整局部`
    : `${{entities.length}} nodes · ${{relations.length}} edges · 滚轮缩放，拖动平移`;
}}
function showEntity(id){{
  const e=S.entities.find(x=>x.canonical_id===id)||{{}};
  const linked=S.relations.filter(r=>r.subject_id===id||r.object_id===id);
  const mentions=M.filter(item=>item.canonical_id===id);
  const aliases=(e.aliases||[]).map(esc).join("、")||"无";
  document.querySelector("#details").innerHTML=
    `<span class="badge info">${{esc(e.entity_type)}}</span><b>${{esc(e.canonical_text)}}</b>
    <p class="mono">${{esc(e.canonical_id)}}</p><p>confidence: ${{pct(e.confidence)}}</p>
    <p>aliases in scope: ${{aliases}}</p><p>linked relations: ${{linked.length}} · source mentions: ${{mentions.length}}</p>
    <p>shared documents: ${{esc(e.shared_document_count??"N/A")}} · endpoint only: ${{esc(e.endpoint_only??false)}}</p>
    <p class="subtle">created ${{esc(e.created_version||"")}}</p>`+
    mentions.slice(0,20).map(item=>`<div class="event"><small>${{esc(item.document_id)}} / ${{esc(item.segment_id)}}</small><br>${{esc(item.mention_text)}}${{item.evidence_text?`<br><span class="subtle">${{esc(item.evidence_text)}}</span>`:""}}</div>`).join("");
}}
function showRelation(id){{
  const r=S.relations.find(x=>x.canonical_relation_id===id)||{{}};
  const ev=EV.filter(x=>x.canonical_relation_id===id);
  const byId=x=>(S.entities.find(e=>e.canonical_id===x)||{{}}).canonical_text||x;
  document.querySelector("#details").innerHTML=
    `<span class="badge info">${{esc(r.predicate)}}</span><b>${{esc(byId(r.subject_id))}} → ${{esc(byId(r.object_id))}}</b>
    <p class="mono">${{esc(id)}}</p><p>confidence: ${{pct(r.confidence)}} · evidence: ${{ev.length}}</p>
    <p>qualifier hash: <span class="mono">${{esc(r.qualifiers_hash||"none")}}</span></p>
    <p>provenance: ${{esc(r.provenance_mode||"active canonical relation")}}</p>`+
    ev.map(e=>`<div class="event"><small>${{esc(e.document_id)}} / ${{esc(e.segment_id)}}</small><br>${{esc(e.evidence_text)}}</div>`).join("");
}}
function controls(){{
  const select=document.querySelector("#predicateFilter");
  [...new Set(S.relations.map(r=>r.predicate))].sort().forEach(p=>{{
    const o=document.createElement("option");o.value=p;o.textContent=p;select.appendChild(o);
  }});
  const source=document.querySelector("#sourceFilter");
  (DATA.document_ids||[]).forEach(documentId=>{{
    const o=document.createElement("option");o.value=documentId;o.textContent=documentId;source.appendChild(o);
  }});
  if(SCOPE.kind==="document"){{
    source.value=SCOPE.document_id||"";
    source.disabled=true;
  }}
  select.onchange=()=>{{graphFilters.predicate=select.value;renderGraph();}};
  source.onchange=()=>{{graphFilters.source=source.value;renderGraph();}};
  document.querySelector("#entitySearch").oninput=event=>{{graphFilters.query=event.target.value.trim();renderGraph();}};
  document.querySelector("#resetView").onclick=resetGraphView;
  graphInteractions();
}}
function graphInteractions(){{
  const svg=document.querySelector("#graph");
  svg.addEventListener("wheel",event=>{{
    event.preventDefault();
    const rect=svg.getBoundingClientRect();
    const px=(event.clientX-rect.left)/rect.width;
    const py=(event.clientY-rect.top)/rect.height;
    const factor=event.deltaY>0?1.16:0.86;
    const nextW=Math.max(baseView.w*.08,Math.min(baseView.w*5,graphView.w*factor));
    const nextH=nextW*(graphView.h/graphView.w);
    graphView.x+=px*(graphView.w-nextW);graphView.y+=py*(graphView.h-nextH);
    graphView.w=nextW;graphView.h=nextH;applyGraphView();
  }},{{passive:false}});
  svg.addEventListener("pointerdown",event=>{{
    dragState={{x:event.clientX,y:event.clientY,view:{{...graphView}}}};
    svg.setPointerCapture(event.pointerId);svg.classList.add("dragging");
  }});
  svg.addEventListener("pointermove",event=>{{
    if(!dragState)return;
    const rect=svg.getBoundingClientRect();
    graphView.x=dragState.view.x-(event.clientX-dragState.x)*dragState.view.w/rect.width;
    graphView.y=dragState.view.y-(event.clientY-dragState.y)*dragState.view.h/rect.height;
    applyGraphView();
  }});
  const endDrag=()=>{{dragState=null;svg.classList.remove("dragging");}};
  svg.addEventListener("pointerup",endDrag);svg.addEventListener("pointercancel",endDrag);
  svg.addEventListener("dblclick",resetGraphView);
}}
function renderTimeline(){{
  document.querySelector("#timeline").innerHTML=(DATA.history||[]).map((v,i)=>
    `<div class="event"><b>${{i===0?'<span class="badge ok">ACTIVE</span>':""}}${{esc(v.version_id)}}</b>
    <div>${{esc(v.patch_id)}} · ${{esc(v.run_id)}}</div><small>${{esc(v.created_at)}}</small></div>`
  ).join("")||'<p class="subtle">暂无已提交版本。</p>';
}}
function renderTrace(){{
  document.querySelector("#trace").innerHTML=(G.agent_trace||[]).map(t=>
    `<div class="trace-row"><span class="step">${{esc(t.step_index)}}</span>
    <span><b>${{esc(t.agent_name)}}</b><br><span class="subtle">${{esc(t.selected_action)}}</span></span>
    <span>EIG ${{Number(t.expected_information_gain||0).toFixed(2)}}</span>
    <span>risk ${{Number(t.risk||0).toFixed(2)}}</span></div>`
  ).join("")||'<p class="subtle">选择带 Agent trace 的 registry 后显示。</p>';
}}
function renderQueries(){{
  const s=G.shadow_evaluation||{{}};
  document.querySelector("#queries").innerHTML=(s.query_results||[]).map(q=>
    `<div class="query"><span>${{q.passed?"✓":"✕"}}</span><span>${{esc(q.description)}}<br>
    <small class="mono">${{esc(q.query_id)}}</small></span>
    <span class="badge ${{q.passed?"ok":"fail"}}">${{q.passed?"PASS":"FAIL"}}</span></div>`
  ).join("")||'<p class="subtle">暂无影子验证记录。</p>';
}}
function renderCertificate(){{
  const shadow=G.shadow_evaluation||{{}};
  const cert=shadow.causal_validation_certificate||{{}};
  const decision=G.evolution_decision||{{}};
  const commit=G.evolution_commit||{{}};
  const history=(DATA.history||[])[0]||{{}};
  const impact=shadow.impact_domain||{{}};
  const solver=shadow.compensation_solver||{{}};
  const hasQueryResults=Array.isArray(shadow.query_results);
  const queryResults=hasQueryResults?shadow.query_results:[];
  const counterfactualChecks=queryResults.reduce(
    (total,q)=>total+(Array.isArray(q.counterfactual_checks)?q.counterfactual_checks.length:0),0
  );
  const causeOperations=[...new Set(queryResults.flatMap(q=>
    q.counterfactual_cause_operation_ids||q.caused_by_operation_ids||[]
  ))].sort();
  const value=(...values)=>{{
    const found=values.find(v=>v!==undefined&&v!==null&&v!=="");
    return found===undefined?"N/A":found;
  }};
  const count=value=>Array.isArray(value)?value.length:"N/A";
  const frozenSummary=(impact.domain_hash||cert.frozen_impact_domain_hash)
    ? `${{count(impact.source_document_ids)}} docs · ${{count(impact.source_segment_ids)}} segments · ${{count(impact.entity_ids)}} entities · ${{count(impact.relation_ids)}} relations`
    : "N/A";
  const fields=[
    ["certificate_id",value(cert.certificate_id,decision.certificate_id,commit.certificate_id,history.certificate_id)],
    ["冻结影响域摘要",frozenSummary],
    ["frozen_impact_domain_hash",value(cert.frozen_impact_domain_hash,impact.domain_hash)],
    ["反事实检查数",hasQueryResults?counterfactualChecks:"N/A"],
    ["反事实原因操作",causeOperations.length?causeOperations.join(", "):(hasQueryResults?"无（0）":"N/A")],
    ["solver mode / optimality",`${{value(cert.solver_mode,solver.solver_mode)}} / ${{value(cert.solver_optimality,solver.optimality)}}`],
    ["commit_manifest_hash",value(commit.commit_manifest_hash,history.commit_manifest_hash)],
    ["accepted_operations_hash",value(commit.accepted_operations_hash,history.accepted_operations_hash)],
    ["提交状态",value(commit.status,history.status)],
    ["registry binding",value(G.binding_status)]
  ];
  document.querySelector("#certificate").innerHTML=fields.map(([key,item])=>
    `<div class="certificate-kv"><span class="key">${{esc(key)}}</span><span class="value mono">${{esc(item)}}</span></div>`
  ).join("");
}}
function renderAudit(){{
  const audit={{
    scope:SCOPE,
    registry_binding:{{
      status:G.binding_status,
      selected_run_id:G.selected_run_id,
      registry_run_ids:G.registry_run_ids,
      registry_path:G.registry_path
    }},
    active_schema:DATA.schema,
    evolution_decision:G.evolution_decision,
    evolution_commit:G.evolution_commit,
    minimal_compensation_patch:(G.shadow_evaluation||{{}}).minimal_compensation_patch,
    merge_decisions:G.merge_decisions,
    graph_patch:G.graph_patch
  }};
  document.querySelector("#audit").textContent=JSON.stringify(audit,null,2);
}}
renderScope();renderMetrics();controls();renderGraph();renderTimeline();renderTrace();renderQueries();renderCertificate();renderAudit();
</script>
</body></html>"""
