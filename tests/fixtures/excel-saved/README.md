# Excel-saved fixtures

Workbooks in this folder were saved by real Excel, so they carry the values
Excel calculated. `tests/test_excel_saved_fixtures.py` recalculates every
formula cell with the Referee (headless LibreOffice) and compares the result
with those saved values.

The folder is empty until someone adds files. Do not generate them with
openpyxl or LibreOffice: such files hold no Excel-calculated values, and the
test fails for them on purpose.

## How to make a fixture (Excel for the web)

1. Generate a sample: `python -m samples.make_discount` (or `make_haunted`,
   `make_scenarios`, `make_traps`). Samples are labelled "generated".
2. Sign in to Excel for the web (a free Microsoft account is enough) and
   upload the generated `.xlsx`.
3. Make a tiny edit so Excel recalculates and saves: change a number and
   change it back, or type a character in an unused cell and delete it.
4. File > Create a Copy > Download a Copy.
5. Name the file after the sample, for example `haunted-excel.xlsx`, and put
   it in this folder.
6. Run `.venv/bin/python -m pytest tests/test_excel_saved_fixtures.py -v`.

Commit the `.xlsx` files here. `.gitignore` ignores workbooks elsewhere but
allows `tests/fixtures/**`.

A fixture that fails shows each cell where the Referee and Excel disagree.
That is a real LibreOffice-versus-Excel difference to document in
`.kiro/steering/excel-semantics.md`, not something to hide.
