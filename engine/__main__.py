"""Infinity Engine CLI.

  python -m engine ingest              build/refresh the vault from sources
  python -m engine status              vault counts by album and status
  python -m engine validate            check every note against ontology.yaml
  python -m engine brief SLUG [SLUG..] write ideation prompt packets
  python -m engine brief --all         packets for every un-analysed song
  python -m engine brief SLUG --run-claude   run packet through claude CLI
                                             and merge the result
  python -m engine merge SLUG FILE     merge an analysis JSON into a note
  python -m engine ingest-audio PATH [--slug S] [--bpm N]
                                       read Suno stems (folder or zip) into
                                       an audio block; attach to a note if
                                       --slug names one in the vault
  python -m engine make SLUG KIND [--tier T] [--dry-run]
                                       assemble a job for a song: grab data,
                                       pick model + compute, build the shot
                                       direction, write the job folder.
                                       KIND = panels|keyframes|video|tts|
                                       lipsync|avatar
  python -m engine advance SLUG STATUS move a song to a new pipeline stage
  python -m engine work [JOB_ID] [--offline] [--server URL]
                                       render queued jobs through ComfyUI on
                                       the GPU box. --offline emits the graphs
                                       it would submit, no GPU needed.
                                       --server points at a pod's ComfyUI.
  python -m engine gui [--port N]      open the local control panel in a
                                       browser (buttons, not the terminal)
  python -m engine doctor [--server URL]
                                       show the wiring: paths, whether ComfyUI
                                       is reachable, runners, queued jobs
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


def cmd_ingest_audio(cfg, args):
    from pathlib import Path

    from .audio import analyse_stems
    source = Path(args.path)
    if not source.exists():
        sys.exit(f"not found: {source}")
    print(f"reading stems from {source.name} ...")
    audio = analyse_stems(source, bpm=args.bpm)
    print(f"\n  {audio['bit_depth']}-bit {audio.get('encoding','')} / "
          f"{audio['sample_rate']} Hz / {audio['channels']}ch, "
          f"{audio['duration_s']}s"
          + (f", {audio['tempo_bpm']} BPM" if audio.get("tempo_bpm") else ""))
    print(f"  arrangement: {audio['arrangement']} "
          f"({audio['arrangement_density']} stems active)\n")
    for s in audio["stems"]:
        mark = "*" if s["active"] else " "
        print(f"  [{mark}] {s['role']:16} {s['group']:8} "
              f"{s['rms_dbfs']:>7} dBFS  {s['file']}")
    print(f"\n  active: {', '.join(audio['active_stems'])}")
    if args.slug:
        vault_dir = resolve(cfg, "vault_dir")
        path = vault.note_path(vault_dir, args.slug)
        if not path.exists():
            sys.exit(f"\nno vault note for --slug {args.slug}; not attached")
        note = vault.read_note(path)
        note.meta["audio"] = audio
        vault.write_note(vault_dir, note)
        print(f"\n  attached audio block to {args.slug}")
    else:
        print("\n  (no --slug given; not attached to a note)")


def cmd_review(cfg, args):
    from .textclean import scan
    notes = vault.all_notes(resolve(cfg, "vault_dir"))
    flagged = 0
    for note in sorted(notes, key=lambda n: n.slug):
        rows = []
        for i, line in enumerate(note.body.splitlines(), 1):
            for reason, tok in scan(line):
                rows.append(f"    L{i:<3} {reason:24} {tok}")
        if rows:
            flagged += 1
            print(f"\n{note.slug}")
            print("\n".join(rows))
    print(f"\n{flagged} song(s) with phrases to double-check. Confirmed fixes "
          "go into CORRECTIONS in engine/textclean.py; re-ingest to apply.")


def cmd_make(cfg, args):
    from . import pipeline
    from .config import load_providers
    vault_dir = resolve(cfg, "vault_dir")
    by_slug = {n.slug: n for n in vault.all_notes(vault_dir)}
    note = by_slug.get(args.slug)
    if note is None:
        sys.exit(f"not in vault: {args.slug}")
    providers = load_providers()
    try:
        plan = pipeline.plan_job(cfg, providers, note, args.kind, args.tier)
    except pipeline.PipelineError as exc:
        sys.exit(str(exc))

    m, r = plan["model"], plan["runner"]
    tier_note = ("" if plan["tier_used"] == plan["tier_asked"]
                 else f"  (asked {plan['tier_asked']}, nearest available)")
    print(f"\n  {note.meta.get('title', note.slug)}  ->  {args.kind}\n")
    print(f"  1 grab data      {note.slug}.md"
          f"{' + audio' if plan['spec']['data']['has_audio'] else ''}")
    print(f"  2 grab model     {m.get('name')}  [{plan['tier_used']}"
          f" {plan['category']}]{tier_note}")
    print(f"                   licence: {m.get('licence')}")
    print(f"  3 align compute  {plan['runner_name']} ({r.get('kind', '?')})")
    print(f"  4 give direction {plan['shot_count']} shots from the line read"
          f" + style block")
    if plan["shot_count"]:
        first = plan["spec"]["direction"]["shots"][0]
        snip = (first["direction"][:80] + "...") if len(
            first["direction"]) > 80 else first["direction"]
        print(f"                   shot 1: {snip}")

    if args.dry_run:
        print("\n  (dry run: nothing written)\n")
        return

    conn = jobs_mod.open_db(resolve(cfg, "db_path"))
    job_dir = jobs_mod.create_job(
        resolve(cfg, "jobs_dir"), conn, song_slug=note.slug, kind=args.kind,
        tier=plan["tier_used"], provider=m.get("name"),
        runner=plan["runner_name"], spec=plan["spec"])
    rel = job_dir.relative_to(cfg["_root"])
    print(f"  5 output lands   {rel}/  (spec.json queued)")
    print(f"  6 evaluate       review results that land in {rel}/results/")
    nxt = plan["next_status"]
    if nxt:
        print(f"  7 next move      engine advance {note.slug} {nxt}\n")
    else:
        print("  7 next move      (attach the output to the song)\n")


def cmd_advance(cfg, args):
    from .site import STATUS_ORDER
    if args.status not in STATUS_ORDER:
        sys.exit(f"status must be one of: {', '.join(allowed)}")
    vault_dir = resolve(cfg, "vault_dir")
    path = vault.note_path(vault_dir, args.slug)
    if not path.exists():
        sys.exit(f"not in vault: {args.slug}")
    note = vault.read_note(path)
    old = note.status
    note.meta["status"] = args.status
    vault.write_note(vault_dir, note)
    from .site import STATUS_ORDER
    if STATUS_ORDER.index(args.status) < STATUS_ORDER.index(old):
        print(f"{args.slug}: {old} -> {args.status}  (moved back)")
    else:
        print(f"{args.slug}: {old} -> {args.status}")


def cmd_gui(cfg, args):
    from .gui import serve
    serve(port=args.port, open_browser=not args.no_browser)


def cmd_doctor(cfg, args):
    """Show the wiring: paths, the ComfyUI touchpoint, runners, jobs. The
    one place to see whether a GPU box is actually reachable."""
    from . import comfy, worker
    from .config import load_providers
    root = cfg["_root"]
    print("Infinity Engine wiring\n")

    print("paths (local, never shipped):")
    for key in ("vault_dir", "jobs_dir", "db_path"):
        p = resolve(cfg, key)
        print(f"  {key:10} {p}  {'ok' if p.exists() else '(missing)'}")

    notes = vault.all_notes(resolve(cfg, "vault_dir"))
    by_status = Counter(n.status for n in notes)
    print(f"\nvault: {len(notes)} songs  "
          + ", ".join(f"{s}:{c}" for s, c in by_status.most_common()))

    ccfg = worker.load_comfy_config(root)
    server = args.server or ccfg.get("server", "http://127.0.0.1:8188")
    client = comfy.ComfyClient(server)
    alive = client.alive()
    reach = "YES" if alive else "no (start ComfyUI, or open an SSH tunnel)"
    print("\nComfyUI touchpoint:")
    print(f"  server    {server}")
    print(f"  reachable {reach}")
    print("  recipes (catalog/comfy.yaml) -> checkpoint each expects:")
    for cat, tiers in (ccfg.get("recipes") or {}).items():
        for tier, r in tiers.items():
            print(f"    {cat}/{tier:8} {r.get('ckpt_name')}")

    providers = load_providers()
    print("\nrunners (providers.yaml) -> where jobs can render:")
    for name, r in (providers.get("runners") or {}).items():
        kind = r.get("kind")
        where = r.get("host") or r.get("service") or "this machine"
        ready = "ready" if (kind == "local" or r.get("host") or r.get("service")) \
            else "host not set"
        print(f"  {name:12} {kind:11} {where:22} {ready}")

    conn = jobs_mod.open_db(resolve(cfg, "db_path"))
    jb = Counter(r[0] for r in conn.execute(
        "SELECT status FROM jobs").fetchall())
    print("\njobs: " + (", ".join(f"{s}:{c}" for s, c in jb.items())
                         or "none yet"))
    if jb.get("queued"):
        print(f"  {jb['queued']} queued -> render with: engine work"
              + ("" if alive else " --offline"))


def cmd_work(cfg, args):
    from . import worker
    jobs_dir = resolve(cfg, "jobs_dir")
    conn = jobs_mod.open_db(resolve(cfg, "db_path"))
    if args.job_id:
        ids = [args.job_id]
    else:
        ids = [r[0] for r in conn.execute(
            "SELECT id FROM jobs WHERE status='queued' ORDER BY created_at"
        ).fetchall()]
    if not ids:
        print("no queued jobs; make one with: engine make SLUG KIND")
        return
    for job_id in ids:
        job_dir = jobs_dir / job_id
        if not (job_dir / "spec.json").exists():
            print(f"skip {job_id}: no spec.json")
            continue
        print(f"\n  {job_id}"
              f"{'  [offline: emitting graphs]' if args.offline else ''}")
        jobs_mod.set_status(conn, job_id, "running")
        try:
            manifest = worker.run_job(
                cfg["_root"], job_dir, offline=args.offline,
                server=args.server,
                on_status=lambda n, tot: print(f"    shot {n}/{tot}", end="\r"))
        except Exception as exc:  # noqa: BLE001 - report and move on
            jobs_mod.set_status(conn, job_id, "failed", notes=str(exc))
            print(f"    failed: {exc}")
            continue
        done = sum(1 for s in manifest["shots"] if s.get("rendered"))
        status = "done" if not args.offline else "queued"
        jobs_mod.set_status(conn, job_id, status,
                            notes=f"{len(manifest['shots'])} shots, "
                            f"{done} rendered, offline={args.offline}")
        rel = (job_dir / "results").relative_to(cfg["_root"])
        print(f"    {len(manifest['shots'])} shots -> {rel}/  "
              f"(manifest.json{', graphs/' if args.offline else ''})")


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
    sub.add_parser("review")
    p_audio = sub.add_parser("ingest-audio")
    p_audio.add_argument("path", help="folder or .zip of Suno WAV stems")
    p_audio.add_argument("--slug", help="vault note to attach the audio block to")
    p_audio.add_argument("--bpm", type=int, help="song tempo (Suno shows it)")
    p_make = sub.add_parser("make")
    p_make.add_argument("slug")
    p_make.add_argument("kind", help="panels | keyframes | video | tts | "
                        "lipsync | avatar")
    p_make.add_argument("--tier", default="standard",
                        choices=["draft", "standard", "premium"])
    p_make.add_argument("--dry-run", action="store_true",
                        help="print the plan without writing a job")
    p_adv = sub.add_parser("advance")
    p_adv.add_argument("slug")
    p_adv.add_argument("status")
    p_work = sub.add_parser("work")
    p_work.add_argument("job_id", nargs="?",
                        help="a job id; omit to run all queued jobs")
    p_work.add_argument("--offline", action="store_true",
                        help="emit ComfyUI graphs without a GPU/server")
    p_work.add_argument("--server",
                        help="ComfyUI URL override, e.g. http://POD_IP:8188")
    p_doctor = sub.add_parser("doctor")
    p_doctor.add_argument("--server", help="ComfyUI URL to test")
    p_gui = sub.add_parser("gui")
    p_gui.add_argument("--port", type=int, default=8765)
    p_gui.add_argument("--no-browser", action="store_true")
    sub.add_parser("jobs")
    sub.add_parser("dashboard")
    sub.add_parser("site")

    args = parser.parse_args()
    if args.command == "brief" and not args.slugs and not args.all:
        parser.error("brief needs song slugs or --all")
    cfg = load_config()
    {"ingest": cmd_ingest, "status": cmd_status, "validate": cmd_validate,
     "brief": cmd_brief, "merge": cmd_merge, "review": cmd_review,
     "ingest-audio": cmd_ingest_audio, "make": cmd_make,
     "advance": cmd_advance, "work": cmd_work, "doctor": cmd_doctor,
     "gui": cmd_gui, "jobs": cmd_jobs, "dashboard": cmd_dashboard,
     "site": cmd_site}[args.command](cfg, args)


if __name__ == "__main__":
    main()
