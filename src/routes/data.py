from fastapi import UploadFile, Depends, APIRouter, status , Request
from fastapi.responses import JSONResponse
from models import ResponseStatus
from helpers.config import get_settings, Settings
from controllers import DataController , ProcessFileController
import logging
import aiofiles
import os
from uuid import UUID
from routes.schemes.data import ProcessRequest ,ProjectData
from models.ProjectDataModel import ProjectDataModel
from models.ChunksDataModel import ChunkDataModel
from models.AssetModel import AssetModel
from models.db_schemes import Project , Asset ,DataChunk
from models.enums.AssetTypeEnum import AssetTypeEnum
from controllers import NLPController


logger = logging.getLogger("uvicorn.error")
data_router = APIRouter(
        prefix="/api/v1/data",
        tags=["api_v1" , "Data"],
    )
# Define the endpoint for creating a new project
@data_router.post("/projects/create")
async def create_project(request:Request, project_data: ProjectData):
    project_model = await ProjectDataModel.create_instance(db_client=request.app.db_client)
    Projectobject = Project(    
        project_name= project_data.project_name,
        description= project_data.description,
        owner= project_data.owner
    )
    new_project = await project_model.create_project(project_data=Projectobject)
    if new_project:
         return JSONResponse(
        status_code=status.HTTP_201_CREATED, 
        content={
            "status": True, 
            # Convert UUID to string here
            "project_id": str(new_project.project_id), 
            "project_name": new_project.project_name, 
            "description": new_project.description, 
            "owner": new_project.owner,
            "message": ResponseStatus.PROJECT_CREATED_SUCCESS.value
        }
    )
    else:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": False, 
            "project_name": project_data.project_name, 
            "description": project_data.description, 
            "owner": project_data.owner,
            "message": ResponseStatus.PROJECT_CREATED_ERROR.value})
# Define the endpoint for uploading a file to a project
@data_router.post("/upload/{project_id}")
async def upload_file(request:Request,project_id: UUID, file: UploadFile , app_settings: Settings=Depends(get_settings)):
    project_model = await ProjectDataModel.create_instance(db_client=request.app.db_client)
    new_project = await project_model.get_project_or_create(project_id)
    # validate file type and size
    controller = DataController()
    is_valid, response_status = controller.validate_uploded_file(file)
     # if file is not valid return error response
    if not is_valid:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": is_valid, 
            "project_id": project_id, 
            "file_name": file.filename,
            "file_type": file.content_type, 
            "file_size": file.size, 
            "message": response_status})
    #project_dir_path = ProjectController().get_project_path(project_id)
    file_path , file_id = controller.generate_unique_filepath(original_filename=file.filename, project_id=project_id)
    # save file to disk
    try:
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):  # Read file in chunks
                await f.write(chunk)
        await file.close()
    except Exception as e:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": False, 
            "project_id": new_project.project_id, 
            "file_name": file.filename,
            "file_type": file.content_type, 
            "file_size": file.size, 
            "message": ResponseStatus.FILE_UPLOAD_ERROR.value})

    # Store Asset metadata in the database
    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)
    logger.info(f"Storing asset metadata for file: {file.filename}, project_id: {project_id}, file_path: {file_path}. file_size: {os.path.getsize(file_path)} bytes")
    asset_resource = Asset(
            asset_project_id= new_project.project_id,
            asset_name= file_id,
            asset_type= AssetTypeEnum.File.value,
            asset_size = os.path.getsize(file_path)
            )
    asset_record= await asset_model.create_asset(asset_resource)

    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": True, 
        "file_name": file.filename,
        "file_type": file.content_type, 
        "file_size": file.size, 
        "file_id": file_id,
        "asset_id": str(asset_record.asset_id),
        "message": ResponseStatus.FILE_UPLODED_SUCCESS.value})
# Define the endpoint for processing a file into chunks
@data_router.post("/processfile/{project_id}")
async def process_file(request:Request,project_id: UUID, process_request: ProcessRequest):
   
   # file_id = process_request.file_id
    chunk_size = process_request.chunk_size
    overlap_size = process_request.overlap_size
    do_reset = process_request.do_reset

    project_model = await ProjectDataModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create(project_id)
    nlp_controller = NLPController(
        vector_db_client= request.app.vector_db_client,
        generation_client= request.app.generation_client,
        embedding_client= request.app.embedding_client,
        template_parser= request.app.template_parser
    )
    chunk_model =await  ChunkDataModel.create_instance(db_client=request.app.db_client)

    process_file_controller = ProcessFileController(project_id)
    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)


    project_files_ids = {}
    if process_request.file_id:
        asset_recrod= await asset_model.get_asset_by_name_and_projectid(process_request.file_id,project.project_id)
        if not asset_recrod:
            return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"status": False, 
                "project_id": project_id, 
                "file_id": process_request.file_id,
                "message": ResponseStatus.FILE_NOT_FOUND_IN_PROJECT.value})
        
        project_files_ids= {
            asset_recrod.asset_id: asset_recrod.asset_name
        }

    else:
        assets = await asset_model.get_all_assets_by_project(project.project_id, AssetTypeEnum.File.value)
        project_files_ids = {
            asset.asset_id: asset.asset_name
            for asset in assets
            }
    # validate if file_id exists in the project
    if not project_files_ids:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"status": False, 
            "project_id": project_id, 
            "file_id": process_request.file_id,
            "message": ResponseStatus.FILE_NOT_FOUND_IN_PROJECT.value})
    inserted_chunks_count = 0
    no_of_proccessed_files = 0
    """Validate if do reset is true delete all existing chunks for the project"""
    if do_reset:
        collection_name = await nlp_controller.create_collection_name(str(project.project_id))
        # delete collection in vector db
        _= await request.app.vector_db_client.drop_collection(collection_name)
        # delete chunks in database
        await chunk_model.delete_chunks_by_project(str(project.project_id))
    # Process each file associated with the project
    for asset_id,file_id in project_files_ids.items():
        logger.info(f"Processing file: {asset_id,file_id} in project {project_id}")
        # Get file content
        file_content = process_file_controller.get_document_content(file_id)
        if not file_content:
            ## TODO: Set Is Procced Flag to False in Asset
            logger.error(f"File not found or could not be loaded: {file_id} in project {project_id}")
            continue
    # Process file into chunks
    file_chunks = process_file_controller.process_file(file_content, chunk_size, overlap_size)
    # Create DataChunk records
    file_chunks_records = [ 
        DataChunk(
                chunk_content=chunk.page_content,
                chunk_metadata= chunk.metadata,
                chunk_order= i+1,
                chunk_project_id=project.project_id,
                chunk_asset_id=asset_id
            )
        for i, chunk in enumerate(file_chunks)
    ]
    
    # Bulk insert chunks
    inserted_chunks_count += await chunk_model.bulk_insert_data_chunks(file_chunks_records)
    no_of_proccessed_files += 1
    # If successfully inserted_count is 0 return error
    if not inserted_chunks_count:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": False, 
            "project_id": project_id, 
            "file_id": file_id,
            "inserted_chunks_count": inserted_chunks_count,
            "no_of_proccessed_files": no_of_proccessed_files,
            "message": ResponseStatus.FILE_PROCESSING_ERROR.value})

    return {
        "project_id": project_id, 
        "file_id": file_id,
        "inserted_chunks_count": inserted_chunks_count,
        "no_of_proccessed_files": no_of_proccessed_files,
        "message": ResponseStatus.FILE_PROCESSED_SUCCESS.value     
    }

