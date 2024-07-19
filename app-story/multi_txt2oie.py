from openie import StanfordOpenIE
import os
import csv

properties = {
    'openie.affinity_probability_cap': 2 / 3,
}


# get the triples from a single document
def process_document(txt, doc_name, output_dir):
    with StanfordOpenIE(properties=properties) as client:
        heading = [["NOUN", "VERB/PREP", "NOUN"]]
        output_file_path = os.path.join(output_dir, doc_name + ".OIE")
        with open(output_file_path, 'w+', encoding="utf8") as resultFile:
            write = csv.writer(resultFile, lineterminator='\n')
            write.writerows(heading)
            for triple in client.annotate(txt):
                write.writerow([triple['subject'], triple['relation'], triple['object']])
                print(triple)
        resultFile.close()


# get the triples from all the documents in a directory
def process_files_in_directory(input_dir, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for filename in os.listdir(input_dir):
        if filename.endswith(".txt"):
            file_path = os.path.join(input_dir, filename)
            with open(file_path, 'r', encoding='utf8') as file:
                text = file.read()
                doc_name = os.path.splitext(filename)[0]  # Get the file name without extension
                process_document(text, doc_name, output_dir)


# Get the directory of the current script
current_dir = os.path.dirname(os.path.abspath(__file__))

# Build the relative path to the data directory
data_dir = os.path.join(current_dir, '..', 'data')

# Specify the input directory
input_directory = os.path.join(data_dir, 'Aesops')

# Specify the output directory
output_directory = os.path.join(data_dir, 'Aesops-OIE')

# Use these paths in your code
print(f"Input directory: {input_directory}")
print(f"Output directory: {output_directory}")

process_files_in_directory(input_directory, output_directory)
