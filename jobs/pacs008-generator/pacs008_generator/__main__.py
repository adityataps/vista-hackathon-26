"""CLI: python -m pacs008_generator --count 20 --error-rate 0.3 --seed 42"""
import argparse
import sys

from .generator import generate_batch
from .errors import load_catalog


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="pacs008_generator",
        description="Generiert CBPR+ pacs.008 Meldungen (XSD-valide) mit "
                    "konfigurierbaren Business-Fehlern.")
    ap.add_argument("--count", type=int, default=10, help="Anzahl Meldungen")
    ap.add_argument("--error-rate", type=float, default=0.3,
                    help="Anteil fehlerhafter Meldungen (0..1)")
    ap.add_argument("--faulty", type=int, default=None,
                    help="Absolute Anzahl fehlerhafter Meldungen "
                         "(ueberschreibt --error-rate)")
    ap.add_argument("--seed", type=int, default=None,
                    help="Seed fuer reproduzierbare Laeufe")
    ap.add_argument("--errors", nargs="*", default=None, metavar="CODE",
                    help="Nur diese Fehlercodes verwenden (siehe --list-errors)")
    ap.add_argument("--out", default="output", help="Output-Verzeichnis")
    ap.add_argument("--list-errors", action="store_true",
                    help="Fehlerkatalog anzeigen und beenden")
    args = ap.parse_args(argv)

    if args.list_errors:
        for e in load_catalog():
            print("%-28s [%s/%s] %s" % (e["code"], e["category"],
                                        e["severity"], e["title"]))
        return 0

    m = generate_batch(count=args.count, error_rate=args.error_rate,
                       faulty=args.faulty, seed=args.seed,
                       error_codes=args.errors, out_dir=args.out)
    faulty = [x for x in m["messages"] if x["is_faulty"]]
    print("Generiert: %d Meldungen (%d fehlerhaft) -> %s/"
          % (len(m["messages"]), len(faulty), args.out))
    for x in faulty:
        e = x["errors"][0]
        print("  %-24s %s: %s" % (x["file"], e["code"], e["detail"]))
    print("Ground Truth: %s/manifest.json" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
