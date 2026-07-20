"""Infinity Engine CLI.

  python -m engine ingest              build/refresh the vault from sources
  python -m engine status              vault counts by album and status
  python -m engine validate            check every note against ontology.yaml
  python -m engine brief SLUG [SLUG..] write ideation prompt packets
  python -m engine brief --all         packets for every un-analysed song
  python -m engine brief SLUG --run-claude   run packet through claude CLI
                                             and merge the result
  python -m engine merge SLUG FILE     merge an analysis JSON into a note
  python -m engine jobs                recent job log
  python -m engine dashboard           regenerate dashboard.html
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter

from . import analyse, ingest, jobs as jobs_mod, vault
from .config import load_config, load_ontology, resolve
from .dashboard import render_dashboard


def cmd_ingest(cfg, args):
    vault_dir = resolve(cfg, "vault_dir")
    sources = cfg.get("sources") or {}
    ran = False
    pack = sources.get("album_pack")
    if pack:
        pack_dir = (cfg["_root"] / pack).resolve()
        if pack_dir.exists():
            counts = ingest.ingest_album_pack(
                pack_dir, vault_dir, allow_albums=cfg.get("albums") or None)
            print(f"album-pack: {counts}")
            ran = True
        else:
            print(f"album-pack source not found: {pack_dir}")
    local = sources.get("local_lyrics")
    if local:
        local_dir = (cfg["_root"] / local).resolve()
        if local_dir.exists():
            counts = ingest.ingest_local_lyrics(local_dir, vault_dir)
            print(f"local-lyrics: {counts}")
            ran = True
        else:
            print(f"local_lyrics source not found: {local_dir}")
    if not ran:
        sys.exit("no sources available; check config.yaml")


def cmd_status(cfg, args):
    notes = vault.all_notes(resolve(cfg, "vault_dir"))
    if not notes:
        sys.exit("vault is empty; run: python -m engine ingest")
    by_status = Counter(n.status for n in notes)
    by_album = Counter(n.meta.get("album", "?") for n in notes)
    print(f"{len(notes)} songs in vault\n")
    print("by status:")
    for status, count in by_status.most_common():
        print(f"  {status:10} {count}")
    print("by album:")
    for album, count in by_album.most_common():
        print(f"  {count:3}  {album}")


def cmd_validate(cfg, args):
    ontology = load_ontology()
    notes = vault.all_notes(resolve(cfg, "vault_dir"))
    bad = 0
    for note in notes:
        problems = vault.validate_note(note, ontology)
        if problems:
            bad += 1
            print(f"{note.slug}: {'; '.join(problems)}")
    print(f"\n{len(notes) - bad}/{len(notes)} notes clean")
    if bad:
        sys.exit(1)


def cmd_brief(cfg, args):
    ontology = load_ontology()
    vault_dir = resolve(cfg, "vault_dir")
    prompts_dir = resolve(cfg, "jobs_dir") / "prompts"
    notes = vault.all_notes(vault_dir)
    if args.all:
        targets = [n for n in notes if n.status == "ingested"]
    else:
        by_slug = {n.slug: n for n in notes}
        missing = [s for s in args.slugs if s not in by_slug]
        if missing:
            sys.exit(f"not in vault: {', '.join(missing)}")
        targets = [by_slug[s] for s in args.slugs]
    if not targets:
        sys.exit("nothing to brief")
    for note in targets:
        packet = analyse.write_prompt_packet(note, ontology, prompts_dir)
        print(f"packet: {packet}")
        if args.run_claude:
            print(f"  running claude for {note.slug} ...")
            raw = analyse.run_claude(analyse.build_prompt(note, ontology))
            result = analyse.parse_analysis(raw)
            analyse.merge_analysis(vault_dir, note.slug, result)
            print(f"  merged, status -> analysed")


def cmd_merge(cfg, args):
    with open(args.file, encoding="utf-8") as fh:
        analysis = analyse.parse_analysis(fh.read())
    note = analyse.merge_analysis(resolve(cfg, "vault_dir"), args.slug,
                                  analysis)
    print(f"{note.slug}: merged, status = {note.status}")


def cmd_jobs(cfg, args):
    conn = jobs_mod.open_db(resolve(cfg, "db_path"))
    rows = jobs_mod.list_jobs(conn)
    if not rows:
        print("no jobs logged yet")
        return
    for row in rows:
        job_id, kind, tier, status, cost, updated = row
        cost_s = f"${cost:.2f}" if cost else "-"
        print(f"{updated}  {status:8} {kind:9} {tier:8} {cost_s:>7}  {job_id}")


def cmd_site(cfg, args):
    from .site import load_catalogue, render_site
    pack_dir = (cfg["_root"] / cfg["sources"]["album_pack"]).resolve()
    notes = vault.all_notes(resolve(cfg, "vault_dir"))
    if not notes:
        sys.exit("vault is empty; run: python -m engine ingest")
    catalogue = load_catalogue(pack_dir)
    allow = cfg.get("albums") or None
    if allow:
        # Keep only allowed albums, ordered as the allowlist lists them,
        # so the site mirrors exactly what the pipeline covers.
        by_slug = {a.get("slug"): a for a in catalogue.get("albums", [])}
        catalogue["albums"] = [by_slug[s] for s in allow if s in by_slug]
    written = render_site(notes, catalogue, cfg["_root"] / "docs")
    print(f"wrote {len(written)} pages under docs/")


def cmd_dashboard(cfg, args):
    notes = vault.all_notes(resolve(cfg, "vault_dir"))
    out = cfg["_root"] / "dashboard.html"
    render_dashboard(notes, out)
    print(f"wrote {out} ({len(notes)} songs)")


def main():
    parser = argparse.ArgumentParser(prog="engine",
                                     description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ingest")
    sub.add_parser("status")
    sub.add_parser("validate")
    p_brief = sub.add_parser("brief")
    p_brief.add_argument("slugs", nargs="*")
    p_brief.add_argument("--all", action="store_true")
    p_brief.add_argument("--run-claude", action="store_true")
    p_merge = sub.add_parser("merge")
    p_merge.add_argument("slug")
    p_merge.add_argument("file")
    sub.add_parser("jobs")
    sub.add_parser("dashboard")
    sub.add_parser("site")

    args = parser.parse_args()
    if args.command == "brief" and not args.slugs and not args.all:
        parser.error("brief needs song slugs or --all")
    cfg = load_config()
    {"ingest": cmd_ingest, "status": cmd_status, "validate": cmd_validate,
     "brief": cmd_brief, "merge": cmd_merge, "jobs": cmd_jobs,
     "dashboard": cmd_dashboard, "site": cmd_site}[args.command](cfg, args)


if __name__ == "__main__":
    main()
