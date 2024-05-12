import os
import requests
import shutil
import gzip
import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes
import time


def decrypt_file(encrypted_data, aes_key, iv):
    cipher = Cipher(algorithms.AES(aes_key), modes.CFB(iv))
    decryptor = cipher.decryptor()
    decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()

    unpadder = padding.PKCS7(128).unpadder()
    unpadded_data = unpadder.update(decrypted_data) + unpadder.finalize()

    return unpadded_data

def decompress_data(compressed_data):
    decompressed_data = gzip.decompress(compressed_data)
    return decompressed_data

def download_file(file_name, backend_url, user_id):
    try:
        # Initialize variables to store decrypted splits and keys
        decrypted_splits = []

        for split_index in range(4):  # Assuming 4 splits
            
            response_split = requests.get(f'{backend_url}/download', params={'user_id': user_id, 'file_name': file_name, 'split_index': split_index})

            if response_split.status_code == 200:
                print(f'Split {split_index} downloaded successfully.')
                split_data = response_split.content

                # Retrieve keys for the split
                response_keys = requests.get(f'{backend_url}/retrieve_keys', params={'user_id': user_id, 'file_name': file_name, 'split_index': split_index})

                if response_keys.status_code == 200:
                    # Decode Base64-encoded public key, encrypted AES key, and private key
                    public_key = serialization.load_pem_public_key(base64.b64decode(response_keys.json()['public_key']), backend=default_backend())
                    encrypted_aes_key = base64.b64decode(response_keys.json()['encrypted_aes_key'])
                    private_key = serialization.load_pem_private_key(base64.b64decode(response_keys.json()['private_key']), password=None, backend=default_backend())
                    iv = base64.b64decode(response_keys.json()['iv'])

                    # Decrypt AES key using private key
                    shared_key = private_key.exchange(ec.ECDH(), public_key)
                    
                    derived_key = HKDF(
                        algorithm=hashes.SHA256(),
                        length=32,
                        salt=None,
                        info=b'AES key',
                        backend=default_backend()
                    ).derive(shared_key)

                    
                    if not isinstance(derived_key, bytes):
                        derived_key = derived_key.encode()  # Convert to bytes if not already

                    start_time = time.time() 
                    cipher = Cipher(algorithms.AES(derived_key), modes.ECB(), backend=default_backend())
                    decryptor = cipher.decryptor()
                    aes_key = decryptor.update(encrypted_aes_key) + decryptor.finalize()
                    end_time = time.time()
                    #print(end_time - start_time)

                    # Decrypt the split
                    decrypted_split = decrypt_file(split_data, aes_key, iv)
                    
                    # Decompress the decrypted split
                    decompressed_split = decompress_data(decrypted_split)
                    
                    # Store the decompressed split
                    decrypted_splits.append(decompressed_split)

                else:
                    print(f'Error retrieving keys for split {split_index}. Status code: {response_keys.status_code}')
                    print(response_keys.text)
            else:
                print(f'Error downloading split {split_index}. Status code: {response_split.status_code}')
                print(response_split.text)

        # Merge the decrypted splits
        decrypted_data = b''.join(decrypted_splits)

        # Write decrypted data to file
        with open(file_name, 'wb') as file:
            file.write(decrypted_data)

        print(f'File {file_name} successfully decrypted and saved.')
        
    except Exception as e:
        print(f'Error: {str(e)}')

if __name__ == '__main__':
    
    file_name = 'testpng.png'
    backend_url = 'http://127.0.0.1:5000'
    user_id = '321'

    download_file(file_name, backend_url, user_id)

      # Record the end time
    
