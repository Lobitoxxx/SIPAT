"""Genera un vault Obsidian desde graphify-out/graph.json para visualizar el grafo.

Uso: python scripts/graphify_obsidian.py
Salida: graphify-out/obsidian/*.md (una nota por nodo + indice)
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRAPH = ROOT / "graphify-out" / "graph.json"
OUT = ROOT / "graphify-out" / "obsidian"


def slug(label, node_id, used):
    base = re.sub(r"[^\w\u00e0-\u00ff]+", "_", label.lower()).strip("_")
    if not base:
        base = "node"
    name = base[:60] or "node"
    candidate = name
    i = 2
    while candidate in used:
        candidate = f"{name}_{i}"
        i += 1
    used.add(candidate)
    return candidate


def main():
    data = json.loads(GRAPH.read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in data["nodes"]}
    out_adj = {nid: [] for nid in nodes}
    in_adj = {nid: [] for nid in nodes}
    for l in data.get("links", []):
        out_adj.setdefault(l["source"], []).append(l)
        in_adj.setdefault(l["target"], []).append(l)

    used = set()
    fnames = {}
    for nid, node in nodes.items():
        fnames[nid] = slug(node.get("label", nid), nid, used)

    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*.md"):
        f.unlink()

    communities = {}
    for n in nodes.values():
        communities.setdefault(n.get("community"), 0)
        communities[n.get("community")] += 1

    for nid, node in nodes.items():
        label = node.get("label", nid)
        lines = [f"# {label}", ""]
        lines.append("```yaml")
        lines.append(f'id: "{nid}"')
        lines.append(f'type: "{node.get("file_type", "")}"')
        lines.append(f'source: "{node.get("source_file", "")}"')
        if node.get("source_location"):
            lines.append(f'location: "{node["source_location"]}"')
        lines.append(f'community: {node.get("community", 0)}')
        if node.get("community_name"):
            lines.append(f'community_name: "{node["community_name"]}"')
        lines.append("```")
        lines.append("")
        if node.get("source_file"):
            lines.append(f"**Fuente:** `{node['source_file']}`")
            if node.get("source_location"):
                lines.append(f"**Ubicación:** `{node['source_location']}`")
            lines.append("")
        out = out_adj.get(nid, [])
        inn = in_adj.get(nid, [])
        if out:
            lines.append("## Conecta con")
            for l in sorted(out, key=lambda x: x.get("relation", "")):
                rel = l.get("relation", "relates")
                conf = l.get("confidence", "")
                tgt = fnames.get(l["target"], l["target"])
                lines.append(f"- [[{tgt}]] _{rel}{' ['+conf+']' if conf else ''}_")
            lines.append("")
        if inn:
            lines.append("## Conectado por")
            for l in sorted(inn, key=lambda x: x.get("relation", "")):
                rel = l.get("relation", "relates")
                src = fnames.get(l["source"], l["source"])
                lines.append(f"- [[{src}]] _{rel}_")
            lines.append("")
        (OUT / f"{fnames[nid]}.md").write_text("\n".join(lines), encoding="utf-8")

    deg = {nid: len(out_adj.get(nid, [])) + len(in_adj.get(nid, [])) for nid in nodes}
    top = sorted(deg, key=lambda x: -deg[x])[:15]
    idx = [
        "# Grafo SIPAT (Obsidian)",
        "",
        f"**{len(nodes)} nodos · {len(data.get('links', []))} enlaces · {len(communities)} comunidades**",
        "",
        "## God nodes (nodos puente)",
        "",
    ]
    for nid in top:
        label = nodes[nid].get("label", nid)
        idx.append(f"- **{label}** — {deg[nid]} conexiones — [[{fnames[nid]}]]")
    idx.append("")
    idx.append("## Comunidades")
    idx.append("")
    for c, count in sorted(communities.items()):
        idx.append(f"- **Comunidad {c}** — {count} nodos")
    idx.append("")
    idx.append("_Generado por `scripts/graphify_obsidian.py` desde graphify-out/graph.json_")
    (OUT / "00 Grafo SIPAT.md").write_text("\n".join(idx), encoding="utf-8")
    print(f"vault obsidian listo: {len(nodes)} notas en {OUT}")


if __name__ == "__main__":
    main()
