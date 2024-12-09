# Crear y manejar excepciones
from fastapi import FastAPI, HTTPException, UploadFile, File
from typing import Optional, List
# Para crear la estructura de los datos
from pydantic import BaseModel
# Conexión a MongoDB
from motor import motor_asyncio
# Manejo de IDs
from bson import ObjectId
# Integración con aws
import boto3

# Configuración de la conexión con MongoDB
MONGO_URI = 'mongodb://localhost:27017'
# Ejecutar el cliente de base de datos
client = motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = client['upiiz']

alumno_collection = db['alumnos']
materia_collection = db['materias']
profesor_collection = db['profesores']
calificacion_collection = db['calificaciones']
inscripcion_collection = db['inscripciones']

# Objeto para interactuar con la API
app = FastAPI()

# Modelos de datos utilizando Pydantic para validar la estructura de la entrada
class Alumnos(BaseModel):
    nombre: str
    apellido: str
    fecha_nacimiento: str
    direccion: str
    foto: Optional[str] = None

class Profesores(BaseModel):
    nombre: str
    apellido: str
    fecha_nacimiento: str
    direccion: str
    especialidad: str
    materias: Optional[List[str]] = []

class Materias(BaseModel):
    nombre: str
    descripcion: str
    profesor_id: Optional[str] = None

class Calificaciones(BaseModel):
    alumno_id: str
    materia_id: str
    calificacion: int

class Inscripcion(BaseModel):
    alumno_id: str
    materia_id: str

# ---------------------------- Configuración AWS ---------------------------

# Excepción para cuando no tenemos credenciales de AWS
from botocore.exceptions import NoCredentialsError
# Definir el servicio y la región de AWS
s3 = boto3.client('s3', region_name='us-east-2')

# Crear el bucket
def crear_bucket(name, region="us-east-2"):
    try:
        if region == 'us-east-1':
            s3.create_bucket(Bucket=name)
        else:
            s3.create_bucket(
                Bucket=name,
                CreateBucketConfiguration={'LocationConstraint': region}
            )
        print(f"El bucket {name} se ha creado")
    except NoCredentialsError:
        print("Las credenciales de AWS no se encontraron")
    except Exception as e:
        print(f"El bucket no se creó: {str(e)}")

bucket = 'sd-upiiz'

# crear_bucket(bucket, 'us-east-2')

# Añadir objetos al bucket
def subir_objetos(file: UploadFile, bucket, object_name=None):
    if object_name is None:
        object_name = file.filename
    try:
        # Subir el archivo directamente desde el objeto UploadFile
        s3.upload_fileobj(file.file, bucket, object_name)
        # Generar y retornar la URL de S3
        return f"https://{bucket}.s3.amazonaws.com/{object_name}"
    except NoCredentialsError:
        raise HTTPException(status_code=403, detail="Credenciales de AWS no encontradas")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al subir archivo a S3: {str(e)}")

# Eliminar objeto de los buckets
def eliminar_objeto(bucket, object_name):
    try:
        s3.delete_object(Bucket=bucket, Key=object_name)
        return f'El objeto {object_name} fue eliminado del {bucket}'
    except s3.exceptions.NoSuchKey:
        raise HTTPException(status_code=404, detail="Objeto no encontrado en S3")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar objeto: {str(e)}")
    except NoCredentialsError:
        raise HTTPException(status_code=403, detail="Credenciales de AWS no encontradas")

# -------------------------------- ALUMNOS --------------------------------

# Obtener todos los alumnos
@app.get("/alumnos/")
async def get_alumnos():
    alumnos = await alumno_collection.find().to_list(None)
    for alumno in alumnos:
        alumno['_id'] = str(alumno['_id'])
    return alumnos

# Obtener alumno por ID
@app.get("/alumnos/{alumno_id}")
async def get_alumno(alumno_id: str):
    alumnos = await alumno_collection.find().to_list(None)
    for alumno in alumnos:
        if alumno_id == str(alumno['_id']):
            alumno['_id'] = str(alumno['_id'])
            return alumno

# Añadir alumno
@app.post('/alumnos/')
async def post_alumno(alumno: Alumnos, file: UploadFile = File(None)):
    if file:
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="El archivo debe ser una imagen.")
        try:
            object_name = f"Alumnos/{file.filename}"
            url = subir_objetos(file, bucket, object_name)
            alumno.foto = url
        except NoCredentialsError:
            raise HTTPException(status_code=403, detail="No se encontraron credenciales de AWS.")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    alumno_data = alumno.dict()
    await alumno_collection.insert_one(alumno_data)
    return alumno

# Eliminar alumno
@app.delete('/alumnos/{alumno_id}')
async def delete_alumno(alumno_id: str):
    alumno = await alumno_collection.find_one({"_id": ObjectId(alumno_id)})

    if not alumno:
        raise HTTPException(status_code=404, detail="Alumno no encontrado")

    # Si el alumno tiene una imagen en S3, elimínala
    if alumno.get('foto'):
        # Extrae el nombre del archivo de la URL de S3
        object_name = alumno['foto'].split('/')[-1]
        eliminar_objeto(bucket, f"Alumnos/{object_name}")

    # Elimina el alumno de la base de datos
    result = await alumno_collection.delete_one({"_id": ObjectId(alumno_id)})
    if result.deleted_count:
        return {'message': 'El alumno y su foto han sido eliminados'}
    else:
        raise HTTPException(status_code=404, detail="Alumno no encontrado")

# -------------------------------- PROFESORES --------------------------------

# Obtener todos los profesores
@app.get("/profesores/")
async def get_profesores():
    profesores = await profesor_collection.find().to_list(None)
    for profesor in profesores:
        profesor['_id'] = str(profesor['_id'])
    return profesores

# Obtener profesor por ID
@app.get("/profesores/{profesor_id}")
async def get_profesor(profesor_id: str):
    profesores = await profesor_collection.find().to_list(None)
    for profesor in profesores:
        if profesor_id == str(profesor['_id']):
            profesor['_id'] = str(profesor['_id'])
            return profesor

# Crear un maestro
@app.post("/profesores/")
async def post_profesor(profesor: Profesores):
    await profesor_collection.insert_one(profesor.dict())
    return{
        'message': 'Profesor añadido'
    }

# Actualizar maestro
@app.put("/profesores/{profesor_id}")
async def put_profesor(profesor_id: str, profesor: Profesores):
    profesores = await profesor_collection.find().to_list(None)
    for profe in profesores:
        if str(profe['_id']) == profesor_id:
            await profesor_collection.update_one(profe, {'$set': profesor.dict()})
            return{
                'message': 'Profesor actualizado'
            }
    raise HTTPException(status_code=404, detail="Materia no encontrada")

# Eliminar maestro
@app.delete("/profesores/{profesor_id}")
async def delete_profesor(profesor_id: str):
    profesores = await profesor_collection.delete_one({"_id": ObjectId(profesor_id)})
    if profesores.deleted_count:
        return{
            'message': 'Profesor eliminado'
            }
    raise HTTPException(status_code=404, detail="Profesor no encontrado")

# -------------------------------- MATERIAS --------------------------------

# Obtener todas las materias
@app.get("/materias/")
async def get_materias():
    materias = await materia_collection.find().to_list(None)
    for materia in materias:
        materia['_id'] = str(materia['_id'])
    return materias

# Obtener materias por ID
@app.get("/materias/{materia_id}")
async def get_materia(materia_id: str):
    materias = await materia_collection.find().to_list(None)
    for materia in materias:
        if materia_id == str(materia['_id']):
            materia['_id'] = str(materia['_id'])
            return materia

# Crear una materia
@app.post("/materias/")
async def post_materia(materia: Materias):
    await materia_collection.insert_one(materia.dict())
    return{
        'message': 'Materia añadida'
        }

# Actualizar materia
@app.put("/materias/{materia_id}")
async def put_materia(materia_id: str, materia: Materias):
    materias = await materia_collection.find().to_list(None)
    for mat in materias:
        if str(mat['_id']) == materia_id:
            await materia_collection.update_one(mat, {'$set': materia.dict()})
            return{
                'message': 'Materia actualizada'
                }
    raise HTTPException(status_code=404, detail="Materia no encontrada")

# Eliminar materia
@app.delete("/materias/{materia_id}")
async def delete_materia(materia_id: str):
    materia = await materia_collection.delete_one({"_id": ObjectId(materia_id)})
    if materia.deleted_count:
        return{ 
            'message': 'Materia eliminada'
            }
    raise HTTPException(status_code=404, detail="Materia no encontrada")

# Asignar materias al profesor
@app.post('/materias/asignar/')
async def asignar_materia_profesor(materia_id: str, profesor_id: str):
    try:
        materia_obj_id = ObjectId(materia_id)
        profesor_obj_id = ObjectId(profesor_id)
    except:
        raise HTTPException(status_code=400, detail="ID de materia o profesor no válido")

    profesor = await profesor_collection.find_one({"_id": profesor_obj_id})
    if not profesor:
        raise HTTPException(status_code=404, detail="Profesor no encontrado")
                   
    materia = await materia_collection.find_one({"_id": materia_obj_id})
    if not materia:
        raise HTTPException(status_code=404, detail="Materia no encontrada")

    # Actualizar la materia con el ID del profesor
    await materia_collection.update_one({"_id": materia_obj_id}, {"$set": {"profesor_id": profesor_obj_id}})
    # Agregar la materia a la lista de materias del profesor
    await profesor_collection.update_one({"_id": profesor_obj_id}, {"$push": {"materias": materia_obj_id}})
    return {"message": "Materia asignada al profesor"}

# -------------------------------- Calificaciones --------------------------------

# Obtener la calificacion de un alumno
@app.get('/calificaciones/alumno/{alumno_id}')
async def obtener_calificaciones_alumno(alumno_id: str):
    try:
        obj_id = ObjectId(alumno_id)
    except:
        raise HTTPException(status_code=400, detail="ID del alumno debe ser un ID válido")

    calificaciones = await calificacion_collection.find({"alumno_id": obj_id}).to_list(None)
    for calificacion in calificaciones:
        calificacion['_id'] = str(calificacion['_id'])
        calificacion['alumno_id'] = str(calificacion['alumno_id'])
        calificacion['materia_id'] = str(calificacion['materia_id'])
    return calificaciones

# Obtener calificaciones de una materia
@app.get('/calificaciones/materia/{materia_id}')
async def get_calificacion_materia(materia_id: str):
    try:
        obj_id = ObjectId(materia_id)
    except:
        raise HTTPException(status_code=400, detail="ID de la materia debe ser un ID válido")

    calificaciones = await calificacion_collection.find({"materia_id": obj_id}).to_list(None)
    for calificacion in calificaciones:
        calificacion['_id'] = str(calificacion['_id'])
        calificacion['alumno_id'] = str(calificacion['alumno_id'])
        calificacion['materia_id'] = str(calificacion['materia_id'])
    return calificaciones

# Agregar calificacion
@app.post('/calificaciones/')
async def post_calificacion(calificacion: Calificaciones):
    # Validar alumno_id y materia_id como ObjectId y verificar si existen en la base de datos
    try:
        alumno_id = ObjectId(calificacion.alumno_id)
        materia_id = ObjectId(calificacion.materia_id)
    except:
        raise HTTPException(status_code=400, detail="ID del alumno o materia debe ser un ID válido")

    alumno = await alumno_collection.find_one({"_id": alumno_id})
    if not alumno:
        raise HTTPException(status_code=404, detail="Alumno no encontrado")

    materia = await materia_collection.find_one({"_id": materia_id})
    if not materia:
        raise HTTPException(status_code=404, detail="Materia no encontrada")

    # Insertar la calificación en la base de datos
    calificacion_data = calificacion.dict()
    calificacion_data["alumno_id"] = alumno_id
    calificacion_data["materia_id"] = materia_id
    await calificacion_collection.insert_one(calificacion_data)
    return calificacion

# -------------------------------- INSCRIPCIONES --------------------------------

# Ver las inscripciones de un alumno
@app.get('/inscripciones/alumno/{alumno_id}')
async def obtener_materias_alumno(alumno_id: str):
    try:
        obj_id = ObjectId(alumno_id)
    except:
        raise HTTPException(status_code=400, detail="ID del alumno debe ser un ID válido")

    inscripciones = await inscripcion_collection.find({"alumno_id": obj_id}).to_list(None)
    for inscripcion in inscripciones:
        inscripcion['_id'] = str(inscripcion['_id'])
        inscripcion['alumno_id'] = str(inscripcion['alumno_id'])
        inscripcion['materia_id'] = str(inscripcion['materia_id'])
    return inscripciones

# Ver las inscripciones del alumno x materia
@app.get('/inscripciones/materia/{materia_id}')
async def obtener_alumnos_materia(materia_id: str):
    try:
        obj_id = ObjectId(materia_id)
    except:
        raise HTTPException(status_code=400, detail="ID de la materia debe ser un ID válido")

    inscripciones = await inscripcion_collection.find({"materia_id": obj_id}).to_list(None)
    for inscripcion in inscripciones:
        inscripcion['_id'] = str(inscripcion['_id'])
        inscripcion['alumno_id'] = str(inscripcion['alumno_id'])
        inscripcion['materia_id'] = str(inscripcion['materia_id'])
    return inscripciones

# Ver las inscripciones de materias x alumnos
@app.get('/inscripciones/alumno/{alumno_id}')
async def obtener_materias_alumno(alumno_id: str):
    try:
        obj_id = ObjectId(alumno_id)
    except:
        raise HTTPException(status_code=400, detail="ID del alumno debe ser un ID válido")

    inscripciones = await inscripcion_collection.find({"alumno_id": obj_id}).to_list(None)
    for inscripcion in inscripciones:
        inscripcion['_id'] = str(inscripcion['_id'])
        inscripcion['alumno_id'] = str(inscripcion['alumno_id'])
        inscripcion['materia_id'] = str(inscripcion['materia_id'])
    return inscripciones

# Inscribir alumno a una materia
@app.post('/inscripciones/')
async def inscribir_alumno(inscripcion: Inscripcion):
    try:
        alumno_obj_id = ObjectId(inscripcion.alumno_id)
        materia_obj_id = ObjectId(inscripcion.materia_id)
    except:
        raise HTTPException(status_code=400, detail="ID de alumno o materia no válido")

    alumno = await alumno_collection.find_one({"_id": alumno_obj_id})
    if not alumno:
        raise HTTPException(status_code=404, detail="Alumno no encontrado")

    materia = await materia_collection.find_one({"_id": materia_obj_id})
    if not materia:
        raise HTTPException(status_code=404, detail="Materia no encontrada")

    # Registrar la inscripción
    inscripcion_data = inscripcion.dict()
    inscripcion_data["alumno_id"] = alumno_obj_id
    inscripcion_data["materia_id"] = materia_obj_id
    await inscripcion_collection.insert_one(inscripcion_data)
    return {"message": "Alumno inscrito en la materia"}