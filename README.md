# EICAT AI
AI tools for assisting in the generation of EICAT assessments.
## Run
To run locally you must first install docker and docker compose. The required services can then be deployed using the configuration in `docker-compose.yml`:
```bash
docker compose up -d --build
```
This will start 4 services needed to run the application:
- **API** The main API used to handle data upload and analysis requests.
- **UI** The web interface front-end to the service.
- **GROBID** A support service for extracting texts from PDF files and converting it to TEI XML format.
- **Stylesheets API** A custom support service that allows access to TEI stylesheets to convert TEI XML to a more simplified MD format for LLMs to process.

## Evaluation
The repository contains evaluation scripts to test the performance of the data extraction module. These scripts can be run using the evaluation CLI. The evalution is split into 3 stages.
### Fetch Data
Firstly the data for the evaluation must be retrieved:
```bash
evals fetch # uv run evals fetch
```
This will retrieve the latest data from GISD and split it into a directory structure based on each reference found. Within each directory will be a series of csv files containing the manual extracted impacts from that reference text (e.g. `gold_impacts_$SPECIES_NAME.csv`) for the evaluators to compare against. There will also be a html page which will link to a scholar search to help you retrieve the reference text PDF fpr evaluation (`reference.html`). For any references you would like to evaluate you must find and download the refernce text in the relevant directory.
### Prepare Data
Once you have fetched the evaluation data you wish to use you must prepare it for evaluation. First ensure that you have started the EICAT-AI services using docker (described above) and then run:
```bash
evals prepare # uv run evals prepare
```
This will find all PDF documents in the evaluation directory and process them using the GROBID and TEI stylesheet service to produce TEI XML, HTML and MD formatted versions of the reference text.
### Run Evaluations
Finally once you have prepared the data you can run the evaluation:
```bash
evals run # uv run evals run
```
This will run the evaluation using the prepared data and print the data extraction results to the console - comparing the LLM extracted data with the gold standard data.

## Deployment
- The EICAT-AI application can also be deployed to AWS infrastructure using Terraform. For deployment instructions see [infrastructure/README.md](infrastructure/README.md).

## Development
### Roadmap 
- [ ] Search string module
- [ ] Paper retrieval module
- [ ] Paper summary and screening module
- [x] Data extraction module
- [x] Data classification module
- [x] Report template generation module
- [ ] Terminology checker module
