from operator import __not__
import boto3
import os
import io
from urllib.parse import urlparse
import tempfile
import subprocess

from fastapi import HTTPException

tool = "libreoffice"
# tool = "soffice"

async def download_file_from_s3(s3_url, local_dir):
    s3_path = s3_url.replace("s3://", "", 1)
    full_path_s3 = s3_path.split("/", 1)[1]
    bucket_name = s3_path.split("/", 1)[0]

    # Create an S3 client
    s3 = boto3.client("s3")

    # Get the filename from the S3 path
    filename = os.path.basename(full_path_s3)
    # Check if the filename has a .docx extension; if not, append it
    if not filename.lower().endswith(".docx"):
        filename += ".docx"
        # print("Modified filename --", filename)

    local_file_path = os.path.join(local_dir, filename)  # Create the full local path
    print("filename in download s3--", filename)
    # print("local_file_path --", local_file_path)
    # Ensure the directory exists
    os.makedirs(local_dir, exist_ok=True)

    # print("bucket_name ", bucket_name)
    # print("s3_path ", s3_path)

    # Download the file
    try:
        s3.download_file(bucket_name, full_path_s3, local_file_path)
        print(f"File downloaded successfully from {s3_url} to {local_file_path}")
    except Exception as e:
        print(f"Error downloading file: {e}")

# Function to read DOCX file from S3 into memory
async def get_file_from_s3(s3_path) -> io.BytesIO:
    try:
        # Initialize the S3 client
        s3_client = boto3.client('s3') 
        # S3 Bucket and DOCX file path
        s3_path = s3_path.replace("s3://", "", 1)
        bucket_name, key = s3_path.split("/", 1)
        # output_filename = s3_path.rsplit('/', 1)[-1].replace(".docx", "")

        # Get the DOCX file from S3 bucket
        response = s3_client.get_object(Bucket=bucket_name, Key=key)
        
        # Read the content of the DOCX file from the response
        file_data = response['Body'].read()

        # Load the DOCX content into a BytesIO buffer
        file_buffer = io.BytesIO(file_data)
        file_buffer.seek(0)  # Rewind to the start of the file
        
        print("file_buffer loaded from S3\n")
        # print(docx_buffer)
        return file_buffer
    except Exception as e:
        print(f"Error reading DOCX file from S3: {e}")
        return ""
    
# Function to convert DOCX to PDF in memory using LibreOffice
async def convert_docx_to_pdf_in_memory(docx_buffer: io.BytesIO,file_extension: str) -> io.BytesIO:
    try:
        if file_extension.lower() not in ['doc', 'docx']:
            raise HTTPException(status_code=400, detail="Unsupported file type. Only .doc and .docx are supported.")
        
        # Create a temporary file for the DOC/DOCX input in memory
        with tempfile.NamedTemporaryFile(suffix=f'.{file_extension.lower()}', delete=False) as temp_doc:
            temp_doc.write(docx_buffer.getvalue())
            temp_docx_path = temp_doc.name
        print(temp_docx_path)

        file_name_pdf = os.path.splitext(os.path.basename(temp_docx_path))[0] + ".pdf"
        print(file_name_pdf)
        # Ensure the custom temporary directory exists
        custom_temp_dir = "./pdf"
        os.makedirs(custom_temp_dir, exist_ok=True)

        # Create the path for the output PDF in the custom temporary directory
        temp_pdf_path = os.path.join(custom_temp_dir, file_name_pdf)

        print(temp_pdf_path)

        # Run LibreOffice in headless mode to convert the DOCX to PDF
        command = [
            tool,
            "--headless",
            "--convert-to", "pdf",
            "--outdir", custom_temp_dir,  # Output to temp directory
            temp_docx_path
        ]

        
        
        # Run the command and capture output
        process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Check if the conversion was successful
        if process.returncode != 0:
            raise Exception(f"LibreOffice conversion failed: {process.stderr.decode()}")
        
        print(temp_pdf_path)
        # Now read the PDF back into memory
        with open(temp_pdf_path, 'rb') as pdf_file:
            pdf_buffer = io.BytesIO(pdf_file.read())
        
        # delete file from temp
        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)

        return pdf_buffer

    except Exception as e:
        print(f"Error: {e}")
        raise Exception(f"There is an issue in conversion!.")
    

# Function to convert XLSX to PDF in memory using LibreOffice
async def convert_xlsx_to_pdf_in_memory(xlsx_buffer: io.BytesIO) -> io.BytesIO:
    try:
        # Create a temporary file for the XLSX input in memory
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as temp_xlsx:
            temp_xlsx.write(xlsx_buffer.getvalue())
            temp_xlsx_path = temp_xlsx.name
        
        print(f"Temporary XLSX file path: {temp_xlsx_path}")

        # Generate output PDF file name based on the input file
        file_name_pdf = os.path.splitext(os.path.basename(temp_xlsx_path))[0] + ".pdf"
        print(f"Generated PDF file name: {file_name_pdf}")

        # Ensure the custom temporary directory exists
        custom_temp_dir = "./pdf"
        os.makedirs(custom_temp_dir, exist_ok=True)

        # Create the path for the output PDF in the custom temporary directory
        temp_pdf_path = os.path.join(custom_temp_dir, file_name_pdf)

        print(f"Temporary PDF file path: {temp_pdf_path}")

        # Run LibreOffice in headless mode to convert the XLSX to PDF
        command = [
            tool,  # The command to run LibreOffice in headless mode
            "--headless",   # Run without UI (headless mode)
            "--convert-to", "pdf",  # Specify output format as PDF
            "--outdir", custom_temp_dir,  # Output directory for the PDF
            temp_xlsx_path  # The input XLSX file path
        ]
        
        # Run the command and capture the output
        process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Check if the conversion was successful
        if process.returncode != 0:
            raise Exception(f"LibreOffice conversion failed: {process.stderr.decode()}")

        print(f"Conversion successful. Output PDF at: {temp_pdf_path}")
        
        # Read the PDF back into memory as a BytesIO object
        with open(temp_pdf_path, 'rb') as pdf_file:
            pdf_buffer = io.BytesIO(pdf_file.read())
        
        # Clean up the temporary files
        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)

        if os.path.exists(temp_xlsx_path):
            os.remove(temp_xlsx_path)

        return pdf_buffer

    except Exception as e:
        print(f"Error converting XLSX to PDF: {str(e)}")
        return None




