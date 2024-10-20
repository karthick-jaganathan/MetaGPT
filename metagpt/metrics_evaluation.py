import os
import time

class EvaluationMetrics:
    def __init__(self, project_path):
        self.project_path = project_path
        self.start_time = None
        self.end_time = None

    def start_timer(self):
        self.start_time = time.time()

    def stop_timer(self):
        self.end_time = time.time()

    def running_time(self):
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None

    def count_code_files(self):
        # Recursively counts all .py files in the project path
        file_count = 0
        for root, dirs, files in os.walk(self.project_path):
            for file in files:
                if file.endswith('.py'):
                    file_count += 1
        return file_count

    def lines_per_file(self):
        # Calculate average lines of code per .py file
        total_lines = 0
        total_files = 0
        for root, dirs, files in os.walk(self.project_path):
            for file in files:
                if file.endswith('.py'):
                    total_files += 1
                    with open(os.path.join(root, file), 'r') as f:
                        total_lines += len(f.readlines())
        if total_files == 0:
            return 0
        return total_lines / total_files

    def total_code_lines(self):
        # Calculate the total number of lines across all .py files
        total_lines = 0
        for root, dirs, files in os.walk(self.project_path):
            for file in files:
                if file.endswith('.py'):
                    with open(os.path.join(root, file), 'r') as f:
                        total_lines += len(f.readlines())
        return total_lines

    def executability(self):
        # Assume executability is the number of successfully executed components
        # For now, we assume everything runs successfully
        return 1  # 1 means executable, 0 means not executable

    def token_usage(self):
        # Mock token usage for now; integrate with actual model's token usage if applicable
        return 19292  # Placeholder value

    def productivity(self):
        # Based on the total lines of code and running time
        total_lines = self.total_code_lines()
        running_time = self.running_time() or 1  # Prevent division by zero
        return total_lines / running_time

    def human_revision_cost(self):
        # Mock value for human revision cost; adjust based on complexity
        return 2.5  # Placeholder value

    def display_metrics(self):
        print(f"Executability: {self.executability()}")
        print(f"Running Time: {self.running_time()} seconds")
        print(f"Token Usage: {self.token_usage()}")
        print(f"Code Files: {self.count_code_files()}")
        print(f"Lines per File: {self.lines_per_file()}")
        print(f"Total Code Lines: {self.total_code_lines()}")
        print(f"Productivity: {self.productivity()}")
        print(f"Human Revision Cost: {self.human_revision_cost()}")
