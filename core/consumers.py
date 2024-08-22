import json
import os
from channels.generic.websocket import AsyncWebsocketConsumer
import docker
import asyncio

class ProjectConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            repo_url = data.get('repo_url')
            test_url = data.get('test_url')

            if not repo_url:
                await self.send_log('No repository URL provided.')
                return

            username = self.get_github_username(repo_url)
            await self.handle_project(username, repo_url, test_url)

        except json.JSONDecodeError:
            await self.send_log('Invalid JSON received.')

    async def send_log(self, message):
        await self.send(text_data=json.dumps({'message': message}))

    def get_github_username(self, url):
        try:
            path = url.split('github.com/')[1]
            username = path.split('/')[0]
            return username
        except IndexError:
            raise ValueError('Invalid GitHub URL')

    async def handle_project(self, username, repo_url, test_url):
        container_name = 'ubuntu_container'
        project_dir = f'/project/{username}'
        client = docker.from_env()

        try:
            container = client.containers.get(container_name)

            await self.run_command(container, f'rm -rf {project_dir}')

            await self.send_log('Cloning repository...')
            clone_command = f'git clone {repo_url} {project_dir}'
            await self.run_command(container, clone_command)

            commands = [
                f"sed -i 's/DB_NAME=.*/DB_NAME=databse/' {project_dir}/.env.example",
                f"sed -i 's/DB_USER=.*/DB_USER=databse_user/' {project_dir}/.env.example",
                f"sed -i 's/DB_PASSWORD=.*/DB_PASSWORD=databse_password/' {project_dir}/.env.example",
                f"sed -i 's/DB_HOST=.*/DB_HOST=databse_host/' {project_dir}/.env.example",
                f"sed -i 's/DB_PORT=.*/DB_PORT=5432/' {project_dir}/.env.example",
                f"sed -i 's/REDIS_HOST=.*/REDIS_HOST=redis_host/' {project_dir}/.env.example",
                f"sed -i 's/REDIS_PORT=.*/REDIS_PORT=6379/' {project_dir}/.env.example",
                f"sed -i 's/REDIS_DB=.*/REDIS_DB=1/' {project_dir}/.env.example"
            ]

            for command in commands:
                await self.run_command(container, command)

            await self.run_command(container, f'cp {project_dir}/.env.example {project_dir}/.env')

            await self.send_log('Removing your tests folder...')
            await self.run_command(container, f'rm -rf {project_dir}/tests')

            await self.send_log('Cloning origin tests folder...')
            await self.run_command(container, f'cp -r /project/tests {project_dir}/')

            await self.run_command(container, f'python3 -m venv {project_dir}/env')

            await self.send_log('Installing requirements.txt ...')
            await self.run_command(container, f'{project_dir}/env/bin/pip install -r {project_dir}/requirements.txt')

            await self.send_log('Checking Redis connectivity...')
            await self.run_command(container, 'redis-cli -h redis_host -p 6379 ping')
            await self.send_log('Redis is connected successfully.')

            await self.send_log('Running Django checks...')
            await self.run_command(container, f'{project_dir}/env/bin/python {project_dir}/manage.py check')

            await self.send_log('Running pytest...')
            await self.run_command(container,
                                   f'{project_dir}/env/bin/pytest {project_dir}/{test_url} --cache-clear -vv --json-report --json-report-file={project_dir}/test_data.json')

            await self.send_log('Task completed successfully.')

        except Exception as e:
            await self.send_log(f'An unexpected error occurred: {e}')

    async def run_command(self, container, command):
        try:
            exec_id = container.client.api.exec_create(container.id, command, stdout=True, stderr=True)
            output = container.client.api.exec_start(exec_id, stream=True)

            async for line in self.iterate_output(output):
                await self.send_log(line)
        except Exception as e:
            await self.send_log(f'Error executing command: {e}')

    async def iterate_output(self, output):
        loop = asyncio.get_event_loop()
        try:
            while True:
                line = await loop.run_in_executor(None, next, output, None)
                if line is None:
                    break
                yield line.decode('utf-8')
        except StopIteration:
            pass
        except Exception as e:
            await self.send_log(f'Error reading output: {e}')
