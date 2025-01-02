import os
import subprocess
import sys
import time
from typing import Optional

from smolagents import Tool, CodeAgent, HfApiModel

# If you're using Selenium, ensure it's installed:
# pip install selenium
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By


# ------------------------------------------------------------------------------
# 1) REQUIREMENTS MANAGER
# ------------------------------------------------------------------------------

class RequirementsManager(Tool):
    name = "requirements_manager"
    description = (
        "Transforms a high-level user request into an actionable set of dev requirements. "
        "Output is text describing what to build in Node & Django, and how to test with Selenium."
    )
    inputs = {
        "user_request": {
            "type": "string",
            "description": "A high-level request from the user needing Node & Django code plus Selenium tests."
        }
    }
    output_type = "string"

    def forward(self, user_request: str) -> str:
        # In reality, you might use an LLM to parse or refine the request in more detail.
        # We'll just produce a minimal text block of "requirements."
        lines = []
        lines.append(f"User Request: '{user_request}'")
        lines.append("Requirements:")
        lines.append("1. Create a minimal Node.js Express server that returns 'Hello World' at '/' on port 3000.")
        lines.append("2. Create a minimal Django project that returns 'Hello World' at '/' on port 8000.")
        lines.append("3. Both projects should be in '/code': node/ and django/ subfolders.")
        lines.append("4. Use Selenium to test each running server in headless Chrome, confirming 'Hello World'.")
        lines.append("5. Provide minimal documentation and run instructions.")
        return "\n".join(lines)


# ------------------------------------------------------------------------------
# 2) SUPER DEVELOPER
#    - Generates Node & Django code under /code
# ------------------------------------------------------------------------------

class SuperDeveloper(Tool):
    name = "super_developer"
    description = (
        "Reads the requirements, creates two projects in /code: one Node/Express, one Django."
    )
    inputs = {
        "requirements": {
            "type": "string",
            "description": "Development requirements text from the Requirements Manager."
        }
    }
    output_type = "string"

    def forward(self, requirements: str) -> str:
        """
        For demonstration, we unconditionally generate:
          - Node project in code/node/
          - Django project in code/django/
        Minimal code that says 'Hello World'
        """

        # 1) NODE PROJECT ------------------------------------------------------
        node_dir = os.path.join("code", "node")
        os.makedirs(node_dir, exist_ok=True)

        # package.json
        package_json = {
            "name": "hello-world-node",
            "version": "1.0.0",
            "scripts": {
                "start": "node index.js"
            },
            "dependencies": {
                "express": "^4.18.2"
            }
        }

        # Write package.json
        import json
        with open(os.path.join(node_dir, "package.json"), "w", encoding="utf-8") as f:
            f.write(json.dumps(package_json, indent=2))

        # index.js with a minimal Express server
        node_js = r"""
const express = require('express');
const app = express();
const port = 3000;

app.get('/', (req, res) => {
  res.send('Hello World');
});

app.listen(port, () => {
  console.log(`Node Express server running on port ${port}`);
});
""".strip()

        with open(os.path.join(node_dir, "index.js"), "w", encoding="utf-8") as f:
            f.write(node_js)

        # 2) DJANGO PROJECT ---------------------------------------------------
        django_dir = os.path.join("code", "django")
        os.makedirs(django_dir, exist_ok=True)

        # We'll create a minimal Django project by calling django-admin startproject
        # for demonstration. This requires `django-admin` to be accessible, or we emulate it.
        # Or we can generate files manually. Let's do the commands approach:
        project_name = "helloproject"

        # If the folder is empty or doesn't have manage.py, create
        manage_py_path = os.path.join(django_dir, project_name, "manage.py")
        if not os.path.exists(manage_py_path):
            # We run 'django-admin startproject helloproject' inside code/django
            try:
                subprocess.run(
                    ["django-admin", "startproject", project_name, "."],
                    cwd=django_dir,
                    check=True
                )
            except subprocess.CalledProcessError as e:
                return f"Error creating Django project: {e}"

        # Now let's create a minimal Django view that says 'Hello World'
        # We'll put it in the default app's urls.py
        django_urls_path = os.path.join(django_dir, project_name, "urls.py")
        django_urls_contents = r"""
from django.contrib import admin
from django.urls import path
from django.http import HttpResponse

def hello_world(request):
    return HttpResponse("Hello World")

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', hello_world, name='hello_world'),
]
""".strip()

        with open(django_urls_path, "w", encoding="utf-8") as f:
            f.write(django_urls_contents)

        # Return success info
        return (
            "Created Node Express project in /code/node\n"
            "Created Django project in /code/django\n"
            "Both should serve 'Hello World' at their respective '/' routes."
        )


# ------------------------------------------------------------------------------
# 3) SUPER TESTER
#    - Installs dependencies, runs Node & Django servers, uses Selenium to test.
# ------------------------------------------------------------------------------

class SuperTester(Tool):
    name = "super_tester"
    description = (
        "Builds/starts Node & Django projects, then uses Selenium to check 'Hello World' at each route."
    )
    inputs = {
        "requirements": {
            "type": "string",
            "description": "The development requirements (for reference)."
        }
    }
    output_type = "string"

    def forward(self, requirements: str) -> str:
        """
        1) Install Node dependencies.
        2) Start Node server on port 3000 in background.
        3) Migrate & start Django server on port 8000 in background.
        4) Use Selenium (headless Chrome) to check each server for 'Hello World'.
        5) Shut everything down, return result.
        """
        log = []

        # 1) Install Node dependencies
        node_dir = os.path.join("code", "node")
        if not os.path.isdir(node_dir):
            return "No /code/node folder found. Did you run SuperDeveloper?"
        log.append("[TEST] Installing Node dependencies with 'npm install'...")
        try:
            subprocess.run(["npm", "install"], cwd=node_dir, check=True)
        except subprocess.CalledProcessError as e:
            return f"Error installing node dependencies: {e}"

        # 2) Start Node server in background
        log.append("[TEST] Starting Node server on port 3000...")
        node_process = subprocess.Popen(
            ["npm", "start"],
            cwd=node_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        time.sleep(3)  # Give the server a moment to spin up

        # 3) Start Django server
        django_dir = os.path.join("code", "django")
        if not os.path.isdir(django_dir):
            # Clean up node server before returning
            node_process.kill()
            return "No /code/django folder found. Did you run SuperDeveloper?"
        log.append("[TEST] Applying Django migrations and starting server on port 8000...")
        try:
            subprocess.run(["python", "manage.py", "migrate"], cwd=django_dir, check=True)
            django_process = subprocess.Popen(
                ["python", "manage.py", "runserver", "8000"],
                cwd=django_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            time.sleep(3)  # Give Django time to start
        except subprocess.CalledProcessError as e:
            node_process.kill()
            return f"Error setting up Django project: {e}"

        # 4) Use Selenium to check each server
        log.append("[TEST] Setting up Selenium (headless Chrome) to test endpoints...")

        # Headless Chrome driver
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        try:
            driver = webdriver.Chrome(options=chrome_options)  # Ensure you have ChromeDriver installed

            # 4a) Test Node
            node_url = "http://localhost:3000"
            driver.get(node_url)
            node_page_text = driver.find_element(By.TAG_NAME, "body").text
            if "Hello World" in node_page_text:
                log.append("[TEST] Node server: PASS (contains 'Hello World').")
            else:
                log.append("[TEST] Node server: FAIL (no 'Hello World').")

            # 4b) Test Django
            django_url = "http://localhost:8000"
            driver.get(django_url)
            django_page_text = driver.find_element(By.TAG_NAME, "body").text
            if "Hello World" in django_page_text:
                log.append("[TEST] Django server: PASS (contains 'Hello World').")
            else:
                log.append("[TEST] Django server: FAIL (no 'Hello World').")

            driver.quit()

        except Exception as e:
            log.append(f"[TEST] Selenium error: {e}")

        # 5) Shutdown servers
        log.append("[TEST] Shutting down servers...")
        node_process.kill()
        django_process.kill()

        return "\n".join(log)


# ------------------------------------------------------------------------------
# 4) MAIN ORCHESTRATION (DEMO)
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    # Create each Tool
    requirements_manager_tool = RequirementsManager()
    super_dev_tool = SuperDeveloper()
    super_tester_tool = SuperTester()

    # Create Agents
    llm_model = HfApiModel("meta-llama/Llama-3.3-70B-Instruct")
    requirements_agent = CodeAgent(tools=[requirements_manager_tool], model=llm_model, verbose=True)
    developer_agent = CodeAgent(tools=[super_dev_tool], model=llm_model, verbose=True)
    tester_agent = CodeAgent(tools=[super_tester_tool], model=llm_model, verbose=True)

    # Simulate user request
    user_request = "Please build Node and Django projects that print Hello World at / route, then test them with Selenium."

    print("===== 1) REQUIREMENTS MANAGER =====")
    refined_reqs = requirements_agent.run(user_request)
    print(refined_reqs)

    print("\n===== 2) SUPER DEVELOPER =====")
    dev_result = developer_agent.run(refined_reqs)
    print(dev_result)

    print("\n===== 3) SUPER TESTER =====")
    test_result = tester_agent.run(refined_reqs)
    print(test_result)

