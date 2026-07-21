# Character reference images

Drop a reference image here named after the character's `id` in
`catalog/cast.yaml`, then set `ref_image: <filename>` on that character and
rebuild the site (studio: Expert mode > Rebuild site, or
`python -m engine site`). It appears on the Cast page and is the visual
anchor for that character's LoRA.

Examples:
- `mozzie.png`  -> Mozzie (Sandy Sports Club mosquito)
- `finnius.png` -> Finnius (Point Lookout Fishing Club dolphin)

Notes:
- Anything in this folder is published with the site. For a look you want
  to keep internal for now, keep the file out of here and just fill in the
  `design:` text so the description is captured without the image going
  public.
- A card only shows its image once the file is actually present, so
  declaring `ref_image:` before the file exists is safe.
