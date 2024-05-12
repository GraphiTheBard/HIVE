from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
import os
import shutil
import tempfile
import hashlib
from flask_pymongo import PyMongo
import base64
import uuid
import time
from flask_cors import CORS
app = Flask(__name__)
app.config['MONGO_URI'] = 'mongodb://localhost:27017/hive'
mongo = PyMongo(app)
CORS(app, resources={r"/signup": {"origins": "*"}})
CORS(app, resources={r"/create_user_dir": {"origins": "*"}})
requests_count = 0
total_request_time = 0
max_latency = 0
min_latency = float('inf')

class Key:
    def __init__(self, user_id, file_name, split_index, public_key_filename, encrypted_aes_key_filename):
        self.user_id = user_id
        self.file_name = file_name
        self.split_index = split_index
        self.public_key_filename = public_key_filename
        self.encrypted_aes_key_filename = encrypted_aes_key_filename



UPLOAD_FOLDER = 'E:/s8 project/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def calculate_file_hash(file_path):
    sha256_hash = hashlib.sha256()
    with open(file_path, 'rb') as file:
        for chunk in iter(lambda: file.read(4096), b''):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def save_file(compressed_file, user_id):
    try:
        filename = secure_filename(compressed_file.filename)

        # Construct the file path to save the compressed file directly in 'uploads/user_id'
        file_directory = os.path.join(app.config['UPLOAD_FOLDER'], user_id)
        if not os.path.exists(file_directory):
            os.makedirs(file_directory)

        # Save the compressed file
        compressed_file_path = os.path.join(file_directory, filename)
        compressed_file.save(compressed_file_path)

        return jsonify({'message': 'Compressed file successfully uploaded.', 'filename': filename}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/upload', methods=['POST'])
def upload_file():
    global requests_count, total_request_time, max_latency, min_latency
    start_time = time.time()
    try:
        requests_count += 1

        # Check if the request contains the file part
        if 'file' not in request.files:
            return jsonify({'error': 'No file part in the request.'}), 400

        file = request.files['file']
        user_id = request.form.get('user_id')
        provided_file_hash = request.form.get('file_hash')

        # Check if user_id parameter is missing
        if not user_id:
            return jsonify({'error': 'Missing user_id parameter.'}), 400

        # Check if a file is selected
        if file.filename == '':
            return jsonify({'error': 'No selected file.'}), 400

        # Save the received file
        filename = secure_filename(file.filename)
        file_directory = os.path.join(app.config['UPLOAD_FOLDER'], user_id)
        if not os.path.exists(file_directory):
            os.makedirs(file_directory)
        file_path = os.path.join(file_directory, filename)
        file.save(file_path)
        provided_file_hash = calculate_file_hash(file_path)


       #sha256_hash = hashlib.sha256()
       #with open(file_path, 'rb') as file:
       #   for chunk in iter(lambda: file.read(4096), b''):
       #      sha256_hash.update(chunk)
       #return sha256_hash.hexdigest()

        
        latency = time.time() - start_time
        total_request_time += latency
        max_latency = max(max_latency, latency)
        min_latency = min(min_latency, latency)
        
        
        

        # Check if the received file hash matches the provided hash in the request
        #
        received_file_hash = calculate_file_hash(file_path)
        if received_file_hash != provided_file_hash:
            os.remove(file_path)  # Delete the corrupted file
            return jsonify({'error': 'File integrity check failed.'}), 400

        # Calculate latency
        

        #print(latency)
        return jsonify({'message': 'File uploaded successfully.'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


    
@app.route('/download', methods=['GET'])
def download_file():
    global requests_count, total_request_time, max_latency, min_latency
    start_time = time.time()
    try:
        filename = request.args.get('file_name')
        uid = request.args.get('user_id')
        split_index = request.args.get('split_index')  # Added for handling split files
       

        if not filename:
            return jsonify({'error': 'Missing filename parameter.'}), 400

        if not uid:
            return jsonify({'error': 'Missing uid parameter.'}), 400

        if not split_index:  # If split_index is None, assume it's the original file
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], uid, filename)
        else:
            # Construct file path for split file
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], uid, f'{filename}.split_{split_index}.gz')

        if not os.path.isfile(file_path):
            return jsonify({'error': 'File not found.'}), 404

        # Open the file in binary mode and read its content
        with open(file_path, 'rb') as file:
            file_content = file.read()

        # Return the file content as bytes
        latency = time.time() - start_time
        total_request_time += latency
        max_latency = max(max_latency, latency)
        min_latency = min(min_latency, latency)

        #print(latency)
        
        return file_content, 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    

@app.route('/delete_file', methods=['DELETE'])
def delete_file():
    try:
        uid = request.args.get('uid')
        filename = request.args.get('filename')
       

        if not uid:
            return jsonify({'error': 'Missing uid parameter.'}), 400

        if not filename:
            return jsonify({'error': 'Missing filename parameter.'}), 400

        user_folder = os.path.join(app.config['UPLOAD_FOLDER'], uid)

        if not os.path.exists(user_folder):
            return jsonify({'error': 'User folder not found.'}), 404

        # Remove split files if any
        split_files = [f for f in os.listdir(user_folder) if f.startswith(filename + '.split')]
        if split_files:
            for split_file in split_files:
                os.remove(os.path.join(user_folder, split_file))

            # Delete keys associated with the split files from the database
            keys_collection = mongo.db.keys
            keys_collection.delete_many({
                'user_id': uid,
                'file_name': filename
            })

            return jsonify({'message': f'Split files for "{filename}" have been deleted successfully.'}), 200
        else:
            return jsonify({'error': f'Split files for "{filename}" not found.'}), 404

    except Exception as e:
        return jsonify({'error': str(e)}), 500




    
@app.route('/list_files', methods=['GET'])
def list_files():
    try:
        
        uid = request.args.get('uid')

        if not uid:
            return jsonify({'error': 'Missing uid parameter.'}), 400

        user_folder = os.path.join(app.config['UPLOAD_FOLDER'], uid)
        
        if not os.path.exists(user_folder):
            return jsonify({'error': 'User folder not found.'}), 404

        
        file_list = os.listdir(user_folder)

        return jsonify({'files': file_list}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    
@app.route('/create_user_dir', methods=['POST'])
def create_user_dir():
    print("here")
    try:
        data = request.json
        user_id = data.get('user_id')

        if not user_id:
            return jsonify({'error': 'Missing user_id parameter.'}), 400

        dir_path = os.path.join(app.config['UPLOAD_FOLDER'], user_id)

        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            return jsonify({'message': f'Directory for user {user_id} created successfully.'}), 200
        else:
            return jsonify({'message': f'Directory for user {user_id} already exists.'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    

@app.route('/store_keys', methods=['POST'])
def store_keys():
    try:
        # Get user ID, file name, split index, and IV from request form data
        user_id = request.form.get('user_id')
        file_name = request.form.get('file_name')
        split_index = request.form.get('split_index')
        
        

        # Get public key, encrypted AES key, and private key from request form data
        public_key = request.form.get('public_key')  # No need to decode
        encrypted_aes_key = request.form.get('encrypted_aes_key')  # No need to decode
        private_key = request.form.get('private_key')  # No need to decode
        iv = request.form.get('iv')  # No need to decode IV


        # Insert the keys into the MongoDB collection
        keys_collection = mongo.db.keys  # Access the collection using mongo.db.keys
        keys_collection.insert_one({
            'user_id': user_id,
            'file_name': file_name,
            'split_index': split_index,
            'iv': iv,
            'public_key': public_key,
            'encrypted_aes_key': encrypted_aes_key,
            'private_key': private_key
        })

        return jsonify({'message': 'Keys stored successfully.'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    

@app.route('/retrieve_keys', methods=['GET'])
def retrieve_keys():
    try:
        user_id = request.args.get('user_id')
        file_name = request.args.get('file_name')
        split_index = request.args.get('split_index')
       

        if not user_id:
            return jsonify({'error': 'Missing user_id parameter.'}), 400

        if not file_name:
            return jsonify({'error': 'Missing file_name parameter.'}), 400

        if not split_index:
            return jsonify({'error': 'Missing split_index parameter.'}), 400

        # Query MongoDB collection to retrieve the key and IV data
        keys_collection = mongo.db.keys
        #user_id = user_id + "_split_" + split_index
        key = keys_collection.find_one({
            'user_id': user_id,
            'file_name': file_name,
            'split_index': split_index
        })

        if not key:
            return jsonify({'error': 'Keys not found for the specified user_id, file_name, and split_index.'}), 404

        # Return the keys and IV as is
        return jsonify({
            'public_key': key['public_key'],
            'encrypted_aes_key': key['encrypted_aes_key'],
            'private_key': key['private_key'],
            'iv': key['iv']
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

#--------------------------------------------------------------------------------------------------------------------

#--------------------------------------------------------------------------------------------------------------------



if __name__ == '__main__':
   
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
 
    app.run(debug=True)
