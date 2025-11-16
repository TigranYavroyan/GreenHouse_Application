# How to Use the Diploma Work Document

## Option 1: Import HTML Directly into Google Docs (Recommended)

1. Open Google Docs in your browser
2. Click **File** → **Open**
3. Click **Upload** tab
4. Select the file: `DIPLOMA_WORK_GoogleDocs.html`
5. Google Docs will automatically convert the HTML to a Google Doc
6. You can then download it as Word (.docx) if needed: **File** → **Download** → **Microsoft Word (.docx)**

## Option 2: Convert HTML to DOCX Online

1. Use an online converter like:
   - https://www.zamzar.com/convert/html-to-docx/
   - https://convertio.co/html-docx/
   - https://cloudconvert.com/html-to-docx

2. Upload `DIPLOMA_WORK_GoogleDocs.html`
3. Download the converted .docx file
4. Open in Google Docs or Microsoft Word

## Option 3: Use Pandoc (If Installed)

If you have pandoc installed on your system:

```bash
cd /home/tigran/Desktop/GreenHouse_Application/docs
pandoc DIPLOMA_WORK_GoogleDocs.html -o DIPLOMA_WORK.docx
```

## Customization

After importing into Google Docs, you can:

1. **Add your information:**
   - Replace `[Your Name]` with your actual name
   - Replace `[Supervisor Name]` with your supervisor's name
   - Update the year if needed

2. **Add visual elements:**
   - Insert architecture diagrams
   - Add screenshots of your application
   - Include performance graphs
   - Add sequence diagrams

3. **Format adjustments:**
   - Adjust fonts and spacing as needed
   - Add page numbers
   - Customize headers and footers
   - Add table of contents (Google Docs can auto-generate this)

4. **Complete appendices:**
   - Add actual code samples
   - Include test results
   - Add screenshots
   - Complete API documentation

## File Location

The diploma work document is located at:
`/home/tigran/Desktop/GreenHouse_Application/docs/DIPLOMA_WORK_GoogleDocs.html`

## Notes

- The document is formatted with proper academic styling (Times New Roman, 12pt, double-spaced sections)
- All sections are included with proper page breaks
- Tables and code blocks are properly formatted
- The document follows standard academic thesis structure

