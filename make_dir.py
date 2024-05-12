import requests

def create_user_dir(backend_url, user_id):
    try:
        response = requests.post(f'{backend_url}/create_user_dir', json={'user_id': user_id})

        if response.status_code == 200:
            print(f'Directory for user {user_id} created successfully on the backend.')
        else:
            print(f'Error creating directory. Status code: {response.status_code}')
            print(response.text)

    except Exception as e:
        print(f'Error: {str(e)}')

if __name__ == '__main__':
    backend_url = 'http://127.0.0.1:5000'
    user_id = "321"  # Replace with the user ID you want to create a directory for

    create_user_dir(backend_url, user_id)
