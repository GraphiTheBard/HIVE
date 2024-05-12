import requests

def list_files(backend_url, uid):
    try:
        response = requests.get(f'{backend_url}/list_files', params={'uid': uid})

        if response.status_code == 200:
            files = response.json().get('files', [])
            unique_file_names = set()
            for file in files:
                file_name = file.replace('.split', '').replace('.gz', '').split('_')[0]  # Removing extensions and suffixes
                unique_file_names.add(file_name)
            print(f'List of unique files for user {uid} in the "uploads" folder: {list(unique_file_names)}')
        else:
            print(f'Error listing files. Status code: {response.status_code}')
            print(response.text)

    except Exception as e:
        print(f'Error: {str(e)}')

if __name__ == '__main__':
    #backend_url = 'http://4.224.48.63:5000'  # Replace with your backend URL
    backend_url = 'http://127.0.0.1:5000'
    uid = '321' 

    list_files(backend_url, uid)
