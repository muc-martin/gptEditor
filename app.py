from flask import Flask, request, jsonify, render_template, send_file
import openai
import os
import subprocess
import re
import tempfile

# Global variable to store temp directory path
temp_dir = tempfile.mkdtemp()

app = Flask(__name__)

def validate_openai_key():
    openai.api_key = os.getenv("OPENAI_API_KEY", "")
    if not openai.api_key:
        raise ValueError("OpenAI API Key not provided as environment variable.")

def remove_unwanted_latex(text):
    # Remove comments (excluding \%)
    text = re.sub(r"(?<!\\)%.*", "", text)

    # Remove unreachable code (iffalse blocks)
    text = re.sub(r"\\iffalse(.*?)\\fi", "", text, flags=re.DOTALL)

    # Remove empty lines
    text = "\n".join(line for line in text.splitlines() if line.strip())

    # Trim leading and trailing whitespace
    text = text.strip()

    return text

def process_text(input_text, system_prompt):
    print('PROCESSING...')
    response = openai.ChatCompletion.create(
        model='gpt-4',
        messages=[
            {'role': 'system',
             'content': system_prompt},
            {'role': 'user',
             'content': f'{input_text}'},
        ],
        temperature=0.7,
        stream = True
    )

    collected_messages = []
    for chunk in response:
        chunk_message = chunk['choices'][0]['delta']  # extract the message
        collected_messages.append(chunk_message)  # save the message
        print(chunk_message.get('content', ''), end='')  # print the message

    # Get corrected text from API response
    print('DONE...')
    edited_text = ''.join([m.get('content', '') for m in collected_messages])
    return edited_text


def store_tex_versions(original_tex, edited_tex):
    with open(os.path.join(temp_dir, "original.tex"), "w") as f:
        f.write("\\documentclass{article}\n\\renewcommand{\\cite}[1]{\\ifcsname b@#1\\endcsname \\cite{#1}\\else [#1]\\fi}\n\\begin{document}\n")
        f.write(original_tex)
        f.write("\n\\end{document}")
    with open(os.path.join(temp_dir, "edited.tex"), "w") as f:
        f.write("\\documentclass{article}\n\\renewcommand{\\cite}[1]{\\ifcsname b@#1\\endcsname \\cite{#1}\\else [#1]\\fi}\n\\begin{document}\n")
        f.write(edited_tex)
        f.write("\n\\end{document}")

def perform_latexdiff():
    with open(os.path.join(temp_dir, "diff.tex"), "w") as diff_file:
        subprocess.run(["latexdiff", os.path.join(temp_dir, "original.tex"), os.path.join(temp_dir, "edited.tex")], stdout=diff_file)

def generate_diff_pdf():
    subprocess.run(["pdflatex", "-interaction=nonstopmode", os.path.join(temp_dir, "diff.tex")], cwd=temp_dir)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/review', methods=['POST'])
def review_latex():
    input_text = request.form.get("input")
    system_prompt = request.form.get("prompt")
    preprocessed_text = remove_unwanted_latex(input_text)
    edited_text = process_text(preprocessed_text, system_prompt)

    store_tex_versions(input_text, edited_text)
    perform_latexdiff()
    generate_diff_pdf()

    return jsonify({"edited_text": edited_text})

@app.route('/api/compare', methods=['POST'])
def compare_latex():
    input_text = request.form.get("input")
    compare_text = request.form.get("compare")

    store_tex_versions(input_text, compare_text)
    perform_latexdiff()
    generate_diff_pdf()

    return jsonify({"success": True})

@app.route('/api/render_latex_diff')
def send_diff_pdf():
    return send_file(os.path.join(temp_dir, "diff.pdf"), mimetype="application/pdf")

if __name__ == '__main__':
    validate_openai_key()
    app.run(debug=True)
