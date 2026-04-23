import os
import docker
from linux_agent import LinuxTool

class DevOpsTool:
    """Tool for creating application code and containerizing it."""
    def __init__(self):
        self.ssh_tool = LinuxTool()
        self.docker_client = docker.from_env()
        self.docker_hub_user = os.getenv("DOCKERHUB_USERNAME")
        self.docker_hub_pass = os.getenv("DOCKERHUB_PASSWORD")

    def create_flask_api_and_dockerfile(self, model_path: str) -> str:
        """Creates the Flask app, Dockerfile, and requirements on the remote server."""
        
        # This is a simplified representation. The tool would SSH and run these commands.
        # For brevity, we are showing the content that would be written to files.
        flask_app_code = """
from flask import Flask, request, jsonify
import pickle

app = Flask(__name__)
model = pickle.load(open('model/house_price_model.pkl', 'rb'))

@app.route('/predict', methods=['POST'])
def predict():
    data = request.get_json(force=True)
    prediction = model.predict([data['features']])
    return jsonify({'prediction': prediction[0]})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
"""
        dockerfile_content = """
FROM python:3.9-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 5000
CMD ["python", "app.py"]
"""
        requirements_content = "flask\ngunicorn\npandas\scikit-learn"

        # Using the LinuxTool to create these files on the remote server
        self.ssh_tool.run(f"mkdir -p model && cp {model_path} model/")
        self.ssh_tool.run(f"echo '{flask_app_code}' > app.py")
        self.ssh_tool.run(f"echo '{dockerfile_content}' > Dockerfile")
        self.ssh_tool.run(f"echo '{requirements_content}' > requirements.txt")
        
        return "Flask API and Dockerfile created successfully on remote server."

    def build_and_push_image(self, image_name: str) -> str:
        """Builds the docker image on the remote server and pushes to Docker Hub."""
        try:
            # This is a simplified representation. A real tool would SSH and run these.
            self.ssh_tool.run(f"docker build -t {self.docker_hub_user}/{image_name}:latest .")
            self.ssh_tool.run(f"docker login -u {self.docker_hub_user} -p {self.docker_hub_pass}")
            self.ssh_tool.run(f"docker push {self.docker_hub_user}/{image_name}:latest")
            return f"Image {self.docker_hub_user}/{image_name}:latest pushed successfully."
        except Exception as e:
            return f"Error building or pushing image: {str(e)}"