import time
import os
import json
import csv
import tiktoken  # For token usage tracking
import psutil  # For memory usage tracking
from radon.complexity import cc_visit  # For code complexity tracking

class MetricsLogger:
    def __init__(self, workspace_dir):
        self.workspace_dir = workspace_dir
        self.metrics = {
            "executability": 0,
            "running_time": 0,
            "token_usage": 0,
            "code_files": 0,
            "total_code_lines": 0,
            "avg_lines_per_file": 0,  # Add the new metric for average lines of code
            "human_revision_cost": 0,
            "code_complexity": 0,
            "memory_usage": 0,
            "error_rate": 0
        }
        self.start_time = None
        self.end_time = None
        self.tokenizer = tiktoken.get_encoding("cl100k_base")  # GPT-3.5 Turbo uses cl100k_base

    def start_timer(self):
        self.start_time = time.time()

    def stop_timer(self):
        self.end_time = time.time()
        self.metrics["running_time"] = round(self.end_time - self.start_time, 2)

    def log_executability(self, success):
        self.metrics["executability"] = 1 if success else 0

    def log_token_usage(self, input_text):
        token_count = len(self.tokenizer.encode(input_text))
        self.metrics["token_usage"] += token_count

    def log_code_statistics(self):
        total_lines = 0
        code_files = []
        all_files = []

        for root, _, files in os.walk(self.workspace_dir):
            for file in files:
                full_path = os.path.join(root, file)
                all_files.append(full_path)

                relative_subfolder = os.path.relpath(root, self.workspace_dir)
                relative_file_path = os.path.join(relative_subfolder, file) if relative_subfolder != '.' else file

                # Target code files based on their extensions
                if file.endswith(('.py', '.html', '.js', '.exe', '.css', '.cpp', '.java', '.sh')):
                    code_files.append(full_path)
                    try:
                        with open(full_path, 'r') as f:
                            lines = f.readlines()
                            line_count = len(lines)
                            total_lines += line_count
                    except Exception as e:
                        print(f"Error reading file {full_path}: {e}")

        self.metrics["code_files"] = len(code_files)
        self.metrics["total_code_lines"] = total_lines

        # Calculate the average lines of code per file
        if code_files:
            avg_lines_per_file = total_lines / len(code_files)
        else:
            avg_lines_per_file = 0

        self.metrics["avg_lines_per_file"] = avg_lines_per_file
        print("Average lines of code per file: {}".format(avg_lines_per_file))

    def log_code_complexity(self):
        total_complexity = 0
        for root, _, files in os.walk(self.workspace_dir):
            for file in files:
                if file.endswith(('.py', '.html', '.js', '.exe', '.css', '.cpp', '.java', '.sh')):
                    full_file_path = os.path.join(root, file)
                    try:
                        with open(full_file_path, 'r') as f:
                            code = f.read()
                            complexity = sum([block.complexity for block in cc_visit(code)])
                            total_complexity += complexity
                    except FileNotFoundError:
                        print(f"File not found: {full_file_path}")
                    except Exception as e:
                        print(f"Error reading {full_file_path}: {e}")

        self.metrics["code_complexity"] = total_complexity

    def log_memory_usage(self):
        process = psutil.Process(os.getpid())
        self.metrics["memory_usage"] = process.memory_info().rss / (1024 * 1024)  # in MB

    def log_error_rate(self, error_count):
        self.metrics["error_rate"] = error_count

    def export_metrics(self, output_format='json'):
        if output_format == 'json':
            output_file = os.path.join(self.workspace_dir, 'execution_metrics.json')
            with open(output_file, 'w') as f:
                json.dump(self.metrics, f, indent=4)
        elif output_format == 'csv':
            output_file = os.path.join(self.workspace_dir, 'execution_metrics.csv')
            with open(output_file, 'w', newline='') as f:
                writer = csv.writer(f)
                for key, value in self.metrics.items():
                    writer.writerow([key, value])
        else:
            raise ValueError("Unsupported format. Use 'json' or 'csv'.")
