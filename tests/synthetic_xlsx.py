"""Independently authored OOXML test fixtures; no production source is read.

Standard-library XML/ZIP code keeps test data explicit and creates no committed
workbooks. These are software test inputs, not user-facing authored spreadsheets.
"""

from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as E
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED


NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PRIVATE_MARKERS = (
    "SYNTHETIC_NAME_NEVER_EXPORT_A", "SYNTHETIC_NAME_NEVER_EXPORT_B",
    "000041_SYNTHETIC_ID", "000042_SYNTHETIC_ID", "SYNTHETIC_SHEET_NEVER_EXPORT",
    "SYNTHETIC_TITLE_NEVER_EXPORT", "SYNTHETIC_GROUP_NEVER_EXPORT",
    "SYNTHETIC_DEMOGRAPHIC_NEVER_EXPORT", "SYNTHETIC_FLAG_NEVER_EXPORT",
)


def col(number):
    value = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        value = chr(65 + remainder) + value
    return value


def node(tag, **attrs):
    return E.Element("{" + NS + "}" + tag, {k: str(v) for k, v in attrs.items()})


@dataclass
class Spec:
    cells: dict = field(default_factory=dict)
    merges: list = field(default_factory=list)
    hidden_rows: set = field(default_factory=set)
    extra_sheet: bool = False
    auto_filter: bool = False

    def put(self, ref, value, style=0):
        self.cells[ref] = (value, style)

    def save(self, path: Path):
        rows = {}
        for ref, (value, style) in self.cells.items():
            row = int("".join(ch for ch in ref if ch.isdigit()))
            rows.setdefault(row, []).append((ref, value, style))
        worksheet = node("worksheet")
        data = E.SubElement(worksheet, "{" + NS + "}sheetData")
        for r in sorted(rows):
            row = node("row", r=r)
            if r in self.hidden_rows:
                row.set("hidden", "1")
            data.append(row)
            for ref, value, style in rows[r]:
                cell = node("c", r=ref, s=style)
                row.append(cell)
                if value is None:
                    continue
                if isinstance(value, dict):
                    if "formula" in value:
                        E.SubElement(cell, "{" + NS + "}f").text = value["formula"]
                        E.SubElement(cell, "{" + NS + "}v").text = "1"
                    else:
                        cell.set("t", "e")
                        E.SubElement(cell, "{" + NS + "}v").text = value["error"]
                elif isinstance(value, str):
                    cell.set("t", "inlineStr")
                    E.SubElement(E.SubElement(cell, "{" + NS + "}is"), "{" + NS + "}t").text = value
                else:
                    cell.set("t", "b" if isinstance(value, bool) else "n")
                    E.SubElement(cell, "{" + NS + "}v").text = str(int(value)) if isinstance(value, bool) else repr(value)
        if self.merges:
            merges = E.SubElement(worksheet, "{" + NS + "}mergeCells", count=str(len(self.merges)))
            for ref in self.merges:
                merges.append(node("mergeCell", ref=ref))
        if self.auto_filter:
            worksheet.append(node("autoFilter", ref="A2:N5"))
        workbook = f'<workbook xmlns="{NS}" xmlns:r="{REL}"><sheets><sheet name="SYNTHETIC_SHEET_NEVER_EXPORT" sheetId="1" r:id="rId1"/>'
        if self.extra_sheet:
            workbook += '<sheet name="SYNTHETIC_EXTRA_SHEET" sheetId="2" r:id="rId3"/>'
        workbook += '</sheets></workbook>'
        styles = f'''<styleSheet xmlns="{NS}">
<numFmts count="1"><numFmt numFmtId="164" formatCode="&quot;text&quot;"/></numFmts>
<fonts count="1"><font><name val="Arial"/></font></fonts>
<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>
<borders count="1"><border/></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="4"><xf numFmtId="0"/><xf numFmtId="9"/><xf numFmtId="10"/><xf numFmtId="164"/></cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''
        files = {
            "[Content_Types].xml": '''<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>''',
            "_rels/.rels": f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="{REL}/officeDocument" Target="xl/workbook.xml"/></Relationships>',
            "xl/workbook.xml": workbook,
            "xl/_rels/workbook.xml.rels": f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="{REL}/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="{REL}/styles" Target="styles.xml"/>' + (f'<Relationship Id="rId3" Type="{REL}/worksheet" Target="worksheets/sheet2.xml"/>' if self.extra_sheet else '') + '</Relationships>',
            "xl/worksheets/sheet1.xml": E.tostring(worksheet),
            "xl/styles.xml": styles,
        }
        if self.extra_sheet:
            files["xl/worksheets/sheet2.xml"] = f'<worksheet xmlns="{NS}"><sheetData/></worksheet>'
        with ZipFile(path, "w") as archive:
            for filename, content in files.items():
                info = ZipInfo(filename, date_time=(2000, 1, 1, 0, 0, 0))
                info.compress_type = ZIP_DEFLATED
                archive.writestr(info, content)


def students(count=3, *, optional=True, reorder=False):
    spec = Spec()
    identity = ["Student Name", "Local ID"]
    if optional:
        identity += ["Special Ed Indicator", "Emergent Bilingual", "Ethnicity"]
    scores = ["Raw Score", "Scale Score", "Percent Score", "Approaches Grade Level (TX)", "Meets Grade Level (TX)", "Masters Grade Level (TX)"]
    if reorder:
        identity[0], identity[1] = identity[1], identity[0]
        scores.reverse()
    start = len(identity) + 1
    end = start + count - 1
    last = end + len(scores)
    spec.put(f"{col(start)}1", "SYNTHETIC_TITLE_NEVER_EXPORT")
    spec.merges = [f'A1:{col(start-1)}1', f'{col(start)}1:{col(last)}1', f'{col(start)}2:{col(end)}2']
    spec.put(f'{col(start)}2', 'All Learning Standards')
    labels = {i + 1: label for i, label in enumerate(identity)}
    labels.update({end + 1 + i: label for i, label in enumerate(scores)})
    for c, label in labels.items():
        spec.put(f'{col(c)}2', label)
        spec.merges.append(f'{col(c)}2:{col(c)}3')
    for i in range(count):
        spec.put(f'{col(start+i)}3', f'7.{i+1}(A.i) [R]')
    for r in (4, 5):
        values = {
            'Student Name': PRIVATE_MARKERS[r-4], 'Local ID': PRIVATE_MARKERS[r-2],
            'Raw Score': 10.5 if r == 4 else 0, 'Scale Score': 1444 if r == 4 else None,
            'Percent Score': 0.625 if r == 4 else 0,
        }
        for c, label in labels.items():
            value = values.get(label, 'SYNTHETIC_FLAG_NEVER_EXPORT' if 'Grade Level' in label else 'SYNTHETIC_DEMOGRAPHIC_NEVER_EXPORT')
            style = 2 if label == 'Percent Score' else 0 if label in ('Raw Score','Scale Score') else 3
            spec.put(f'{col(c)}{r}', value, style)
        for i in range(count):
            spec.put(f'{col(start+i)}{r}', [0, 0.625, None][i % 3] if r == 4 else [1, None, 0.5][i % 3], 1)
    spec.put(f'{col(last+1)}5', None, 3)
    return spec


def items(count=5, *, reorder=False):
    spec = Spec()
    spec.put('B1', 'SYNTHETIC_TITLE_NEVER_EXPORT')
    spec.merges = ['A1:A2', 'B1:E1', f'A3:A{count+2}']
    spec.put('A3', 'SYNTHETIC_GROUP_NEVER_EXPORT')
    labels = ['Total Students','Question Number','Learning Standard Number','Student Correct']
    if reorder:
        labels.reverse()
    for c, label in enumerate(labels,2):
        spec.put(f'{col(c)}2', label)
    for i in range(count):
        values = {'Total Students':2,'Question Number':i+1,'Learning Standard Number':f'7.{i%3+1}.A.i','Student Correct':[0,0.625,None][i%3]}
        for c, label in enumerate(labels,2):
            spec.put(f'{col(c)}{i+3}', values[label], 2 if label == 'Student Correct' else 0)
    return spec
