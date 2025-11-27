import io
from fastapi import APIRouter, HTTPException, status, Query
from utils.ran_part_one.aws_s3_utils import get_file_from_s3, convert_docx_to_pdf_in_memory, convert_xlsx_to_pdf_in_memory
from fastapi.responses import StreamingResponse
from utils.db_utils import postgres_get_kb_file
# from utils.logger import logger
ranQueryopenfilev2 = APIRouter(prefix='/watsonx/ran', tags=['RAN - Docs Open/Download'])


# local_xlsx_path = "/Users/prakashb/Desktop/Dish/dish_rca_space/dish-ran/pdf/2023_06_23_INCWLS0436076_Multus_Token_Expiry_BHM_v01.pdf"
# local_xlsx_path = "/Users/prakashb/Desktop/Dish/dish_rca_space/dish-ran/pdf/2023_06_23_INCWLS0436076_Multus_Token_Expiry_BHM_v01.docx"

# local_xlsx_path = "/Users/prakashb/Desktop/Dish/dish_rca_space/dish-ran/Dish_SEA_GPL_Parameters_v24.07.30 (1).xlsx"

# def get_docx_from_local(local_xlsx_path) -> io.BytesIO:
#    try:
#         with open(local_xlsx_path, "rb") as docx_file:
#             docx_buffer = io.BytesIO(docx_file.read())
#         docx_buffer.seek(0)  # Rewind to the start of the file
#         print("docx_buffer---\n")
#         print(docx_buffer)
#         return docx_buffer
#    except Exception as e:
#         print(f"Error reading DOCX file: {e}")
#     #    raise

async def convert_file_to_pdf(file_buffer: io.BytesIO, file_extension: str) -> io.BytesIO:
    if file_extension.lower() == 'docx' or  file_extension.lower() == 'doc':
        return await convert_docx_to_pdf_in_memory(file_buffer,file_extension)
    elif file_extension.lower() == 'xlsx':
        return await convert_xlsx_to_pdf_in_memory(file_buffer)
    elif file_extension.lower() == 'pdf':
        return file_buffer  # No conversion needed for PDF files
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type")


@ranQueryopenfilev2.get("/ran_open_file_v2",
                      summary="RAN document based on filename ",
                      status_code=status.HTTP_200_OK,
                      response_description= 'RAN Document - pdf or xlsx'
                      )
async def ran_open_file(file_name: str = Query(..., description="file name ")):
    try:
        #s3_file_url = "s3://dl-dish-wrls-whlsl-network-documents-cpni-p/rca/2024-05-15/_2024_05_15_INCWLS0734602_CHGWLS0064910_DEF_16656_5_DET_AOI_sites_not_taking_traffic_RRC_rejection_Final.docx"
        print("file name-->", file_name)

        s3_file_url = postgres_get_kb_file(file_name)

        if s3_file_url != "NA":

            # Step 1: Get the file from S3 into memory (use utility function)
            file_buffer = await get_file_from_s3(s3_file_url)
            # file_buffer = get_docx_from_local(local_xlsx_path)

            # Extract file extension to determine how to convert the file
            file_extension = s3_file_url.split('.')[-1]
            # print(f"File Extension: {file_extension}")

            # Step 2: Convert the file to PDF in memory based on file type
            if file_extension == 'xlsx':
                file_buffer.seek(0)
                headers = {
                    "Content-Disposition": f"attachment; filename={s3_file_url.split('/')[-1]}"
                }
                return StreamingResponse(file_buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers)
            else:
                pdf_buffer = await convert_file_to_pdf(file_buffer, file_extension)

                # Step 3: Return the PDF as a StreamingResponse (this will allow downloading directly)
                pdf_buffer.seek(0)  # Rewind buffer to start before sending
                # print(pdf_buffer)

                #output_filename = 'converted'
                headers = {
                    "Content-Disposition": f"inline; filename={s3_file_url.split('/')[-1]}"
                }
                return StreamingResponse(pdf_buffer, media_type="application/pdf", headers=headers)
            # return FileResponse(pdf_buffer, media_type='application/pdf', filename=f"{output_filename}.pdf", headers={"Content-Disposition": "inline; filename=" + f"{output_filename}.pdf"})
        else:
            return HTTPException(status_code=404, detail=f"File not found.")
    except Exception as e:
        return HTTPException(status_code=404, detail=f"Sorry!, Unable to load the document!.")




