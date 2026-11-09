# PAST-YEAR-PAPER-downloader-and-compiler
## Astris Downloader
Downloads and compiles past papers for CIE exams like IGCSE and A-Levels.
#
### Collaborators
MD Rakibul Hasan [https://github.com/mdrakibulhasan615]  
Mohammad Saadaan [https://github.com/strawdile]
#
### 🔑 Google Sheets API Setup
This application logs compiled master PDF metadata directly to a central Google Sheet via a Google Cloud Service Account.

1. Enable the **Google Sheets API** and **Google Drive API** in your Google Cloud Console.
2. Create a **Service Account** and generate a JSON key.
3. Rename the downloaded key file to `credentials.json` and place it in the root directory of this project.
4. Open your target Google Sheet (e.g "`ASTRIS Data`") and share **Editor** permissions with your Service Account email:
   e.g "`astris@astris-dwnloader.iam.gserviceaccount.com`"
