"""
ফাইলের নাম  : file_parser.py
ফাইলের কাজ  : বিভিন্ন ধরনের file থেকে text extract করে
               
               Support করে:
               → PDF  : PyPDF2 দিয়ে text বের করে
               → CSV  : Pandas দিয়ে rows read করে
               → XML  : xml.etree দিয়ে parse করে
               → TXT  : সরাসরি read করে
               
কে use করে  : knowledge_base.py (file upload endpoint এ)
সংযুক্ত     : rag_service.py (extracted text পাঠায়)

Flow:
Agency File Upload করে
        ↓
file_parser.py → text extract করে
        ↓
rag_service.py → ChromaDB তে save করে
"""

import io
import csv
import xml.etree.ElementTree as ET
import PyPDF2
from typing import Optional


# ============================================
# MAIN PARSER FUNCTION
# কাজ : File type দেখে সঠিক parser call করে
# কে call করে : knowledge_base.py
# ============================================
async def parse_file(
    file_content: bytes,
    file_name: str,
    file_type: str
) -> Optional[str]:
    """
    কাজ  : File type অনুযায়ী সঠিক parser select করে text বের করে
    নেয়  : file_content (bytes), file_name, file_type
    দেয়  : extracted text (string)
    কখন : Agency file upload করলে

    Supported types:
    → pdf  → parse_pdf()
    → csv  → parse_csv()
    → xml  → parse_xml()
    → txt  → parse_txt()
    """

    print(f"\n📄 Parser: Starting | File: {file_name} | Type: {file_type}")

    file_type = file_type.lower().strip(".")

    if file_type == "pdf":
        text = await parse_pdf(file_content, file_name)

    elif file_type == "csv":
        text = await parse_csv(file_content, file_name)

    elif file_type == "xml":
        text = await parse_xml(file_content, file_name)

    elif file_type == "txt":
        text = await parse_txt(file_content, file_name)

    else:
        print(f"❌ Parser: Unsupported file type | Type: {file_type}")
        return None

    if text:
        print(f"✅ Parser: Done | File: {file_name} | Characters: {len(text)}")
    else:
        print(f"❌ Parser: No text extracted | File: {file_name}")

    return text


# ============================================
# PDF PARSER
# কাজ : PDF file থেকে text বের করে
# ============================================
async def parse_pdf(file_content: bytes, file_name: str) -> Optional[str]:
    """
    কাজ  : PDF file থেকে সব pages এর text বের করে
    নেয়  : file_content (bytes)
    দেয়  : full text (string)

    উদাহরণ:
    Input : insurance_policy.pdf (50 pages)
    Output: "Policy Terms and Conditions... Premium Details..."
    """

    try:
        pdf_file = io.BytesIO(file_content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)

        total_pages = len(pdf_reader.pages)
        print(f"📑 PDF: Total pages: {total_pages}")

        all_text = []

        for page_num, page in enumerate(pdf_reader.pages, 1):
            page_text = page.extract_text()
            if page_text:
                all_text.append(f"[Page {page_num}]\n{page_text}")
                print(f"   Page {page_num}: {len(page_text)} characters")

        full_text = "\n\n".join(all_text)
        print(f"✅ PDF: Extracted | Total: {len(full_text)} characters")
        return full_text

    except Exception as e:
        print(f"❌ PDF: Failed | Error: {str(e)}")
        return None


# ============================================
# CSV PARSER
# কাজ : CSV file থেকে text বের করে
# ============================================
async def parse_csv(file_content: bytes, file_name: str) -> Optional[str]:
    """
    কাজ  : CSV file এর সব rows text এ convert করে
    নেয়  : file_content (bytes)
    দেয়  : formatted text (string)

    উদাহরণ:
    Input : products.csv
    ┌──────────┬──────────┬────────┐
    │ Plan     │ Premium  │ Cover  │
    ├──────────┼──────────┼────────┤
    │ Basic    │ 500 taka │ 2 lakh │
    │ Family   │ 1200 taka│ 5 lakh │
    └──────────┴──────────┴────────┘

    Output: "Plan: Basic, Premium: 500 taka, Cover: 2 lakh..."
    """

    try:
        content = file_content.decode("utf-8")
        csv_reader = csv.DictReader(io.StringIO(content))

        all_rows = []
        row_count = 0

        for row in csv_reader:
            # প্রতিটা row কে readable text এ convert করো
            row_text = " | ".join([
                f"{key}: {value}"
                for key, value in row.items()
                if value  # empty values skip করো
            ])
            all_rows.append(row_text)
            row_count += 1

        full_text = "\n".join(all_rows)
        print(f"✅ CSV: Extracted | Rows: {row_count} | Characters: {len(full_text)}")
        return full_text

    except Exception as e:
        print(f"❌ CSV: Failed | Error: {str(e)}")
        return None


# ============================================
# XML PARSER
# কাজ : XML file থেকে text বের করে
# ============================================
async def parse_xml(file_content: bytes, file_name: str) -> Optional[str]:
    """
    কাজ  : XML file এর সব elements এর text বের করে
    নেয়  : file_content (bytes)
    দেয়  : extracted text (string)

    উদাহরণ:
    Input : insurance_plans.xml
    <plans>
      <plan>
        <name>Basic</name>
        <premium>500</premium>
      </plan>
    </plans>

    Output: "plan: name: Basic premium: 500..."
    """

    try:
        root = ET.fromstring(file_content.decode("utf-8"))

        def extract_xml_text(element, depth=0):
            """XML tree থেকে recursively text বের করে"""
            texts = []
            indent = "  " * depth

            # Element এর নিজের text
            if element.text and element.text.strip():
                texts.append(f"{indent}{element.tag}: {element.text.strip()}")

            # Attributes
            for attr, value in element.attrib.items():
                texts.append(f"{indent}{attr}: {value}")

            # Child elements
            for child in element:
                texts.extend(extract_xml_text(child, depth + 1))

            return texts

        all_texts = extract_xml_text(root)
        full_text = "\n".join(all_texts)

        print(f"✅ XML: Extracted | Elements: {len(all_texts)} | Characters: {len(full_text)}")
        return full_text

    except Exception as e:
        print(f"❌ XML: Failed | Error: {str(e)}")
        return None


# ============================================
# TXT PARSER
# কাজ : Plain text file সরাসরি read করে
# ============================================
async def parse_txt(file_content: bytes, file_name: str) -> Optional[str]:
    """
    কাজ  : Plain text file সরাসরি read করে
    নেয়  : file_content (bytes)
    দেয়  : text (string)
    """

    try:
        text = file_content.decode("utf-8")
        print(f"✅ TXT: Extracted | Characters: {len(text)}")
        return text

    except Exception as e:
        print(f"❌ TXT: Failed | Error: {str(e)}")
        return None


# ============================================
# GET FILE TYPE FROM NAME
# কাজ : File name থেকে extension বের করে
# ============================================
def get_file_type(file_name: str) -> str:
    """
    কাজ  : File name থেকে extension বের করে
    নেয়  : file_name (যেমন: "policy.pdf")
    দেয়  : extension (যেমন: "pdf")

    উদাহরণ:
    "insurance.pdf" → "pdf"
    "products.csv"  → "csv"
    "plans.xml"     → "xml"
    """
    return file_name.split(".")[-1].lower()