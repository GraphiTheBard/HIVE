import requests

def delete_file(backend_url, uid, filename):
    try:
        response = requests.delete(f'{backend_url}/delete_file', params={'uid': uid, 'filename': filename})

        if response.status_code == 200:
            print(f'File "{filename}" and its splits have been deleted successfully.')
        else:
            print(f'Error deleting file "{filename}". Status code: {response.status_code}')
            print(response.text)

    except Exception as e:
        print(f'Error: {str(e)}')

if __name__ == '__main__':
    #backend_url = 'http://4.224.48.63:5000'  # Replace with your backend URL
    backend_url = 'http://127.0.0.1:5000'
    uid = '321' 
    filename = 'testpng.png' 

    delete_file(backend_url, uid, filename)