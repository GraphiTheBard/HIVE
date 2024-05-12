import os
import requests
import tempfile
import shutil
import gzip
import base64
import hashlib
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import time

def calculate_file_hash(file_path):
    sha256_hash = hashlib.sha256()
    with open(file_path, 'rb') as file:
        for chunk in iter(lambda: file.read(4096), b''):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()

def split_and_compress_file(file_path, num_splits):
    temp_dir = tempfile.mkdtemp()
    split_file_paths = []
    try:
        with open(file_path, 'rb') as file:
            chunk_size = os.path.getsize(file_path) // num_splits
            for i in range(num_splits):
                split_file_path = os.path.join(temp_dir, f'{os.path.basename(file_path)}.split_{i}.gz')
                with open(split_file_path, 'wb') as split_file:
                    chunk = file.read(chunk_size)
                    with gzip.open(split_file_path, 'wb') as compressed_file:
                        compressed_file.write(chunk)
                    split_file_paths.append(split_file_path)
    except Exception as e:
        shutil.rmtree(temp_dir)  # Clean up temporary directory
        raise e
    return split_file_paths

def encrypt_file(file_path):
    start_time = time.time()
    with open(file_path, 'rb') as file:
        plaintext = file.read()

    aes_key = os.urandom(32) 
    iv = os.urandom(16)  

    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(plaintext) + padder.finalize()

    cipher = Cipher(algorithms.AES(aes_key), modes.CFB(iv))
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded_data) + encryptor.finalize()
    encryption_time = time.time() - start_time
    #print(encryption_time)
    return ciphertext, aes_key, iv, encryption_time

def send_file(file_path, backend_url, user_id):
    try:
        # Generate private key
        start_time = time.time()
        private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
        key_gen_time = time.time() - start_time

        # Serialize private key
        serialized_private_key = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )

        # Split and compress the file
        compressed_file_paths = split_and_compress_file(file_path, num_splits=4)
        
        for split_index, compressed_file_path in enumerate(compressed_file_paths):

            # Encrypt each compressed split file
            encrypted_data, aes_key, iv, encryption_time = encrypt_file(compressed_file_path)
            iv = base64.b64encode(iv).decode()
            original_filename = os.path.basename(file_path)
            #print(compressed_file_path)
            split_file_hash = calculate_file_hash(compressed_file_path)

            # Define key data for storage
            key_data = {
                'user_id': f'{user_id}_split_{split_index}',
                'file_name': original_filename,
                'split_index': split_index,
                'public_key_filename': f'public_key_{split_index}.pem',
                'encrypted_aes_key_filename': f'encrypted_aes_key_{split_index}.bin',
                'private_key_filename': f'private_key_{split_index}.pem',
                'iv': iv,
                'split_file_hash': split_file_hash  # Include the hash of the split file
            }
            # Get public key
            public_key = private_key.public_key()

            serialized_public_key = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )

            # Exchange keys
            shared_key = private_key.exchange(ec.ECDH(), public_key)

            derived_key = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=None,
                info=b'AES key',
                backend=default_backend()
            ).derive(shared_key)

            cipher = Cipher(algorithms.AES(derived_key), modes.ECB(), backend=default_backend())
            encryptor = cipher.encryptor()
            encrypted_aes_key = encryptor.update(aes_key) + encryptor.finalize() 

            files = {
                'file': (f'{original_filename}.split_{compressed_file_path.split("_")[-1]}', encrypted_data, 'application/octet-stream')
            }

            data = {
                'user_id': user_id,
                'public_key': base64.b64encode(serialized_public_key).decode(),  # Encode public key in base64
                'encrypted_aes_key': base64.b64encode(encrypted_aes_key).decode(),  # Encode encrypted AES key in base64
                'private_key': base64.b64encode(serialized_private_key).decode(),
                'iv': iv,  # Encode private key in base64
                'split_file_hash': split_file_hash
            }

            response = requests.post(f'{backend_url}/upload', files=files, data=data)

            if response.status_code == 200:
                print(f'File {original_filename} successfully uploaded on the backend.')
            else:
                print(f'Error uploading file {original_filename}. Status code: {response.status_code}')
                print(response.text)

            response = requests.post(
                f'{backend_url}/store_keys',
                data={
                    'user_id': user_id,
                    'file_name': original_filename,
                    'split_index': split_index,
                    'public_key': base64.b64encode(serialized_public_key).decode(),  # Encode public key in base64
                    'encrypted_aes_key': base64.b64encode(encrypted_aes_key).decode(),  # Encode encrypted AES key in base64
                    'private_key': base64.b64encode(serialized_private_key).decode(),  # Encode private key in base64
                    'iv': iv,
                }
            )

            if response.status_code == 200:
                print(f'Keys for file {original_filename} split {split_index} successfully stored.')
            else:
                print(f'Error storing keys for file {original_filename} split {split_index}. Status code: {response.status_code}')
                print(response.text)

        # Clean up temporary directory
        shutil.rmtree(os.path.dirname(compressed_file_paths[0]))

      #  print(f'Encryption time: {encryption_time} seconds')
       # print(f'Key generation time: {key_gen_time} seconds')

        # Get sizes of keys
        private_key_size = len(serialized_private_key)
        public_key_size = len(serialized_public_key)
        aes_key_size = len(aes_key)
        iv_size = len(iv)

       # print(f'Private key size: {private_key_size} bytes')
       # print(f'Public key size: {public_key_size} bytes')
       # print(f'AES key size: {aes_key_size} bytes')
       # print(f'IV size: {iv_size} bytes')

    except Exception as e:
        print(f'Error: {str(e)}')

if __name__ == '__main__':
    file_path = 'testpng.png'  
    backend_url = 'http://127.0.0.1:5000' 
    user_id = '321'
    send_file(file_path, backend_url, user_id)
