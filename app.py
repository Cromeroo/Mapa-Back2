from flask import Flask
from flask import request, jsonify
from flask_cors import CORS
from ee_utils import *
from flask_caching import Cache
from datetime import date
import ee

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:5173"}})
cache = Cache(app, config={'CACHE_TYPE': 'simple'})


@app.before_request
def before():
    ee.Initialize()


@app.route('/')
def hello_world():
    return 'Hello World!'

def maskS2clouds(image):
    qa = image.select('QA60')
    cloudBitMask = 1 << 10
    cirrusBitMask = 1 << 11
    mask = qa.bitwiseAnd(cloudBitMask).eq(0) \
        .And(qa.bitwiseAnd(cirrusBitMask).eq(0))
  
    return image.updateMask(mask).divide(10000)


def obtener_fecha_actual():
    today = date.today()
    fecha_actual = today.strftime("%Y-%m-%d")
    return fecha_actual


@app.route('/coords', methods=['POST'])
def process_coordinates():
    # Obtener las coordenadas del payload
    data = request.get_json()
    coordinates = data.get('coordinates', [])

    # Convertir las coordenadas en una geometría de Earth Engine
    polygon = ee.Geometry.Polygon(coordinates)

    # Cargar la colección de imágenes y seleccionar la primera imagen
    image = ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR').first()

    # Recortar la imagen al polígono proporcionado
    image_clipped = image.clip(polygon)

    # Definir los parámetros de visualización (mismos que se usaban anteriormente)
    vis_params = {
        'bands': ['temperature_2m'],
        'min': 250,
        'max': 320,
        'palette': [
            '000080', '0000d9', '4000ff', '8000ff', '0080ff', '00ffff',
            '00ff80', '80ff00', 'daff00', 'ffff00', 'fff500', 'ffda00',
            'ffb000', 'ffa400', 'ff4f00', 'ff2500', 'ff0a00', 'ff00ff',
        ]
    }

    url_data = image_to_map_id(image_clipped, vis_params)
    if 'errMsg' in url_data:
        return jsonify({"error": url_data['errMsg']}), 500
    return jsonify({"url": url_data['url']}), 200

@app.route('/precipitation', methods=['POST'])
def process_precipitation():
    data = request.get_json()
    coordinates = data.get('coordinates', [])

    # Convertir las coordenadas en una geometría de Earth Engine
    polygon = ee.Geometry.Polygon(coordinates)

    # Cargar la colección de imágenes de precipitaciones
    precipitation_collection = ee.ImageCollection('NASA/GPM_L3/IMERG_MONTHLY_V06').select('precipitation')

    # Podemos elegir procesar de alguna manera estas imágenes, como promediarlas.
    # Aquí, como ejemplo, simplemente tomamos la primera imagen.
    precipitation_image = precipitation_collection.first()

    # Recortar la imagen de precipitaciones al polígono proporcionado
    precipitation_clipped = precipitation_image.clip(polygon)

    # Definir los parámetros de visualización para la capa de precipitaciones
    vis_params = {
        'min': 0,
        'max': 500,
        'palette': ['blue', 'limegreen', 'yellow', 'red']
    }

    # Obtener la URL de la capa de precipitaciones
    url_data = image_to_map_id(precipitation_clipped, vis_params)
    if 'errMsg' in url_data:
        return jsonify({"error": url_data['errMsg']}), 500

    return jsonify({"url": url_data['url']}), 200


@app.route('/ndvi', methods=['GET'])
def calculate_ndvi():
    # Initialize the Earth Engine object.
    ee.Initialize()

    # Carga Sentinel-2 data and calculate NDVI.
    dataset = (ee.ImageCollection('COPERNICUS/S2')
           .filterDate('2023-2-03', obtener_fecha_actual())
           .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 50))
           .map(maskS2clouds))
    
    ndvi = dataset.map(lambda image: image.normalizedDifference(['B8', 'B4']))
    mean_ndvi = ndvi.mean()
    
    # Configuración de visualización del NDVI
    ndvi_vis = {
        'min': -1,
        'max': 1,
        'palette': ['blue', 'white', 'green']
    }
    
    # Generate a URL that can be used to retrieve the NDVI data.
    ndvi_url = mean_ndvi.getThumbURL({
        'min': -1, 'max': 1, 'dimensions': 512, 'format': 'png', 'palette': ['blue', 'white', 'green']
    })
    
    # Returns the NDVI data as a URL that can be used to display the image.
    return jsonify({'ndvi_url': ndvi_url})


if __name__ == "_main_":
    app.run(port = 5000, debug = True)