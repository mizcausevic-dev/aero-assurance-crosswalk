# Aerospace assurance crosswalk

**Draft, informative reference.** This is a vertical extension of the Kinetic Gain Protocol Suite, not an airworthiness approval, regulatory filing, or certification checklist. Source status was checked on **2026-10-12**.

The [crosswalk data](data/crosswalk.json) relates proposed Aviation ML Assurance Card and MRO AI Sign-off Card fields to public aviation sources. It states applicability and limits per row. [`index.html`](index.html) is a generated static reading view of the same rows.

Mapped field paths are checked against byte-pinned copies of the two source JSON Schemas in [`schemas/`](schemas/). The pins are [Aviation ML Assurance Card `6995c124`](https://github.com/mizcausevic-dev/aviation-ml-assurance-card-spec/blob/6995c12453a5ac588b7d9c1de5d285fed7fe2fe1/aviation-ml-card.schema.json) and [MRO AI Sign-off Card `c3cf35b8`](https://github.com/mizcausevic-dev/mro-ai-signoff-card-spec/blob/c3cf35b8955194266d70eb855b307ddb6c1bd1dd/mro-ai-signoff-card.schema.json). Their SHA-256 digests are enforced in [`scripts/render.py`](scripts/render.py). These snapshots make the check reproducible; they do not automatically detect later upstream schema changes. Re-pin and review the field mappings whenever either source schema changes.

## Read the boundaries first

- [EASA NPA 2025-07](https://www.easa.europa.eu/en/document-library/notices-of-proposed-amendment/npa-2025-07) remains proposed material. Its comment period closed on 2026-03-10. EASA's proposed table reserves Level 3B.
- The [FAA AI Safety Assurance Roadmap](https://www.faa.gov/aircraft/air_cert/step/roadmap_for_AI_safety_assurance) is a roadmap, not a certification basis.
- [EUROCAE WG-114](https://www.eurocae.net/working-group/wg-114/) lists ED-324 as a draft, with a target publication date of 2026-12-31. Do not assert compliance against unpublished objectives.
- ARP4754B and DO-178C are separately licensed standards with different scopes. This public crosswalk cites identifiers and the publishers' public descriptions only. It does not reproduce text or invent objective IDs. See [EUROCAE's use policy](https://www.eurocae.net/ed-distribution-and-use-policy/).
- A dataset hash or review signature establishes neither dataset origin nor maintenance-release authority. The MRO card is evidence for a human workflow. It is not a certificate of release to service.
- NIST AI RMF 1.0 is voluntary. The rows indicate topics for review, not a pass/fail compliance score.

## Rebuild and check

Python 3.10+ with only the standard library:

```powershell
py -3 scripts/render.py --check
py -3 -m unittest discover -s tests -v
```

To regenerate the page after changing `data/crosswalk.json`:

```powershell
py -3 scripts/render.py --write
```

The checks validate internal source links, field paths against the pinned JSON Schemas, row uniqueness, source status, and deterministic HTML output. They do not fetch live external URLs or establish regulatory correctness. Re-check the source status before reusing the mappings for a release.

## License

MIT for this original crosswalk data, code, and page. Source material remains under its publisher's own terms. See [LICENSE](LICENSE).
