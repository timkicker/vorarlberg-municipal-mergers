# Municipal mergers in Vorarlberg

Code for the study *Municipal mergers in Vorarlberg. What the evidence says for and against* (`paper/paper.pdf`) and its two-page German summary (`paper/kurzfassung.pdf`). The study asks what merging some of Vorarlberg's 96 municipalities would change for administration costs, revenue, one-off costs, services and local democracy. The Styrian reform of 2015 is the test case.

## Reproduction

You need Python 3.13 with [uv](https://docs.astral.sh/uv/), GNU make and `pdftotext` from poppler-utils.

```sh
uv sync
make data      # downloads the raw data into data/raw (about 1.7 GB)
make results   # all calculations and the figure data into data/derived, then the tests
make figures   # the data behind the figures, in data/derived/figures
```

A few inputs have to be placed in `data/raw/` by hand. `DATA.md` lists them together with every source, its licence and the tables the scripts write. If one of them is missing, the step that needs it prints a note and the result file from the repository stays in `data/derived/`. Before `make data` the tests are skipped. The road network step (`roads.py`) reads the whole OpenStreetMap extract of Austria and is the slowest one. Downloads are retried a few times and files that are already there with the same URL and checksum are skipped. `python src/gf/fetch.py --force` loads everything again.

## Layout

- `src/gf/` holds one script per step in the order of the Makefile and a few helper modules. Each script prints its results and writes them to `data/derived/`.
- `data/derived/` holds the result files as used for the paper, apart from the few that `DATA.md` names as not passed on. `make results` writes them again.
- `data/raw/` holds only four small tables typed by hand. Everything else is downloaded there.
- `tests/` checks the derived data, for example complete codes, contiguous units and matching totals.
- `paper/` has the paper and the German summary as PDF.

## Citation

Kicker, T. (2026). *Municipal mergers in Vorarlberg: What the evidence says for and against*. Zenodo. https://doi.org/10.5281/zenodo.24444247

The code itself can be cited with `CITATION.cff`.

## Licence

The code is under the MIT licence (`LICENSE`). The paper and the German summary are under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Data keep the licence of their source, see `DATA.md`.
