# Re-run manifest

Run dir: `D:\Major Project\evaluation\results\rerun_2026-10-10`

## Environment

```
date: 2026-10-10T12:36:51
git commit: 7db6ff7e0635570e499d8e6fd7c7e1a863f9d7c8
git branch: jonan
git status --short:
M README.md
 M claude.md
 M evaluation/results/adversarial_gap_probes_corpus2.json
 M numbers.md
?? RAG_System_Observation_Log.md
?? Trust_Before_Text_NLPIR.pdf
?? evaluation/rerun_suite.py
?? experiments/_adaptive_full_log.txt
?? experiments/_adaptive_full_log2.txt
?? experiments/_adaptive_smoke_log.txt
?? experiments/_fullrun_log.txt
?? experiments/_fullrun_log2.txt
?? experiments/_fullrun_log3.txt
?? experiments/_fullrun_log4.txt
?? experiments/_hardening_cleanafter_log.txt
?? experiments/_hardening_cleanbefore_log.txt
?? experiments/_hardening_inject_log.txt
?? experiments/_hardening_injsmoke_log.txt
?? experiments/_haystack_full_log.txt
?? experiments/_haystack_smoke_log.txt
?? experiments/_injection_full_log.txt
?? experiments/_injection_full_log2.txt
?? experiments/_injection_smoke_log.txt
?? experiments/_ourdecisions_log.txt
?? experiments/_scale_full_log.txt
?? experiments/_scale_smoke_log.txt
?? experiments/_smoke_log.txt
?? paper_assets/trust_before_text.tex.bak
python: 3.11.9 (tags/v3.11.9:de54cf5, Apr  2 2024, 10:12:12) [MSC v.1938 64 bit (AMD64)]
pip freeze:
accelerate==1.14.0
aiohappyeyeballs==2.6.2
aiohttp==3.13.5
aiosignal==1.4.0
altair==6.0.0
annotated-doc==0.0.4
annotated-types==0.7.0
anyio==4.12.1
attrs==26.1.0
bcrypt==5.0.0
beautifulsoup4==4.15.0
blinker==1.9.0
blis==1.3.3
brotli==1.2.0
build==1.5.0
cachetools==7.0.5
catalogue==2.0.10
certifi==2026.1.4
cffi==2.0.0
charset-normalizer==3.4.4
chromadb==1.5.9
click==8.3.1
cloudpathlib==0.25.0
cloudpickle==3.1.2
colorama==0.4.6
confection==1.3.3
contourpy==1.3.3
cryptography==48.0.1
cssselect2==0.9.0
cycler==0.12.1
cymem==2.0.13
defusedxml==0.7.1
distro==1.9.0
durationpy==0.10
en_core_web_sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl#sha256=1932429db727d4bff3deed6b34cfc05df17794f4a52eeb26cf8928f7c1a0fb85
fairlearn==0.14.0
faiss-cpu==1.13.2
fastapi==0.139.0
filelock==3.20.3
Flask==3.1.3
flask-cors==6.0.5
flatbuffers==25.12.19
fonttools==4.62.1
fpdf2==2.8.7
frozenlist==1.8.0
fsspec==2026.1.0
gitdb==4.0.12
GitPython==3.1.46
googleapis-common-protos==1.75.0
greenlet==3.5.0
groq==0.37.1
grpcio==1.80.0
h11==0.16.0
h2==4.3.0
hf-xet==1.2.0
hpack==4.2.0
httpcore==1.0.9
httptools==0.7.1
httpx==0.28.1
huggingface_hub==1.3.7
hyperframe==6.1.0
idna==3.11
importlib_resources==7.1.0
iniconfig==2.3.0
itsdangerous==2.2.0
Jinja2==3.1.6
jiter==0.15.0
joblib==1.5.3
jsonpatch==1.33
jsonpointer==3.0.0
jsonschema==4.26.0
jsonschema-specifications==2025.9.1
kiwisolver==1.5.0
kubernetes==36.0.0
langchain-core==1.2.8
langchain-groq==1.1.2
langsmith==0.6.8
llvmlite==0.49.0
loguru==0.7.3
lxml==6.1.1
Markdown==3.10.2
markdown-it-py==4.2.0
MarkupSafe==3.0.3
matplotlib==3.11.1
mdurl==0.1.2
mmh3==5.2.1
mpmath==1.3.0
multidict==6.7.1
murmurhash==1.0.15
narwhals==2.18.1
nest-asyncio==1.6.0
networkx==3.6.1
nltk==3.9.4
numba==0.67.0
numpy==2.4.2
oauthlib==3.3.1
onnxruntime==1.26.0
openai==2.38.0
opentelemetry-api==1.42.1
opentelemetry-exporter-otlp-proto-common==1.42.1
opentelemetry-exporter-otlp-proto-grpc==1.42.1
opentelemetry-proto==1.42.1
opentelemetry-sdk==1.42.1
opentelemetry-semantic-conventions==0.63b1
orjson==3.11.7
overrides==7.7.0
packaging==26.0
pandas==3.0.2
patsy==1.0.2
phonenumbers==9.0.39
pillow==12.2.0
playwright==1.59.0
plotly==6.6.0
pluggy==1.6.0
portalocker==3.2.0
preshed==3.0.13
presidio_analyzer==2.2.364
presidio_anonymizer==2.2.364
propcache==0.5.2
protobuf==6.33.6
psutil==7.2.2
pyarrow==23.0.1
pybase64==1.4.3
pycparser==3.0
pydantic==2.12.5
pydantic-settings==2.14.1
pydantic_core==2.41.5
pydeck==0.9.1
pydyf==0.12.1
pyee==13.0.1
Pygments==2.20.0
PyMuPDF==1.27.2.3
pyngrok==8.1.2
pyparsing==3.3.2
pypdf==6.6.2
PyPDF2==3.0.1
pyphen==0.17.2
PyPika==0.51.1
pyproject_hooks==1.2.0
pytest==9.1.1
python-dateutil==2.9.0.post0
python-docx==1.2.0
python-dotenv==1.2.1
python-multipart==0.0.32
pywin32==312
PyYAML==6.0.3
qdrant-client==1.18.0
rank-bm25==0.2.2
referencing==0.37.0
regex==2026.1.15
requests==2.32.5
requests-file==3.0.1
requests-oauthlib==2.0.0
requests-toolbelt==1.0.0
rich==15.0.0
rpds-py==0.30.0
safetensors==0.7.0
scikit-learn==1.8.0
scipy==1.17.0
seaborn==0.13.2
sentence-transformers==5.2.2
sentencepiece==0.2.2
shap==0.51.0
shellingham==1.5.4
six==1.17.0
slicer==0.0.8
smart_open==8.0.1
smmap==5.0.3
sniffio==1.3.1
soundfile==0.14.0
soupsieve==2.9.2
spacy==3.8.16
spacy-legacy==3.0.12
spacy-loggers==1.0.5
srsly==2.5.3
starlette==1.3.1
statsmodels==0.14.6
streamlit==1.56.0
sympy==1.14.0
tabulate==0.10.0
tenacity==9.1.2
thinc==8.3.13
threadpoolctl==3.6.0
tiktoken==0.12.0
tinycss2==1.5.1
tinyhtml5==2.1.0
tldextract==5.3.2
tokenizers==0.22.2
toml==0.10.2
torch==2.10.0
tornado==6.5.5
tqdm==4.67.2
transformers==5.0.0
typer==0.25.1
typer-slim==0.21.1
typing-inspection==0.4.2
typing_extensions==4.15.0
tzdata==2026.1
urllib3==2.6.3
uuid_utils==0.14.0
uvicorn==0.47.0
wasabi==1.1.3
watchdog==6.0.0
watchfiles==1.2.0
weasel==1.0.0
weasyprint==68.1
webencodings==0.5.1
websocket-client==1.9.0
websockets==16.0
Werkzeug==3.1.8
win32_setctime==1.2.0
Windows-Toasts==1.3.1
winrt-runtime==3.2.1
winrt-Windows.Data.Xml.Dom==3.2.1
winrt-Windows.Foundation==3.2.1
winrt-Windows.Foundation.Collections==3.2.1
winrt-Windows.UI.Notifications==3.2.1
wrapt==2.4.1
xxhash==3.6.0
yarl==1.24.2
zopfli==0.4.1
zstandard==0.25.0
```

## Steps

| step | status | exit | seconds |
|---|---|---|---|
| model_download | done | 0 | 83.7 |
| ingest_c1_c2 | done | 0 | 75.3 |
| clear_cache | done | 0 | 0.0 |
| eval_c1 | done | 0 | 83.8 |
| eval_c2 | done | 0 | 99.2 |
| eval_c1_gateoff | done | 0 | 59.4 |
| eval_c2_gateoff | done | 0 | 190.9 |
| invariance_c1 | done | 0 | 490.6 |
| invariance_c2 | done | 0 | 734.1 |
| containment | done | 0 | 61.1 |
| gap_probes_c1 | done | 0 | 44.3 |
| gap_probes_c2 | done | 0 | 48.4 |
| fabricated_c1 | done | 0 | 35.8 |
| fabricated_c2 | done | 0 | 37.6 |
| label_audit | done | 0 | 25.1 |
| pytest | failed | 2 | 3.4 |
| collect | not run |  |  |

## Result files (SHA-256)

| file | sha256 | bytes |
|---|---|---|
| adversarial_gap_probes_corpus1.json | 78273fcac21324173729546af9e8ec8316dc273a56169e9830b1dac502097e64 | 8209 |
| adversarial_gap_probes_corpus2.json | df1d11e94f083a0f5b61f8d80aa269177196e422a8dccb8b0d6cb2a73886a29f | 8216 |
| fabricated_evidence_corpus1.json | 6a952b95565af93b679e1af6971353a21c3fb601161a182a8773e26e95b5ed8c | 2554 |
| fabricated_evidence_corpus2.json | 3078ceb96a1fabbb8bff817e3318a9ec5690ea7c55cf7711705b6e6670137f73 | 2550 |
| invariance_corpus1.json | 5d7bef7449601564e878bbf07c0cc7edcd7d1f6ab2fd5c9f47ada5a07b82609a | 1070 |
| invariance_corpus2.json | 3e879e99219213aaae7957049c75edad79cf34d4f06e747a0eb9f8f46c2580aa | 1262 |
| label_audit.json | 34ab5c4eb8415b166f0f84807abb2af47a6a84f2c9cade0cbacd160029051b7f | 13306 |
| rerun_ahoff_corpus1.json | cfbfa0f49c34f77a37a9a1a6d13d19d8266bcc1ff03f884de8e1994d2353fe8e | 46494 |
| rerun_ahoff_corpus2.json | cc8abf6eaf5759a2421353d7e2aa5bdfe2017f41b227744e82c2a10d65d5d653 | 51027 |
| rerun_console.err | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | 0 |
| rerun_console.log | 6bc17a200bd91d4a6284d7f3d60fb37cf7e2b9e5567a9351c33194aa2cfe9119 | 1501 |
| rerun_corpus1.json | 7419e6d757bffe854d11237b9ecc1e983bfd83e223695185ab8a35cffab84c37 | 46446 |
| rerun_corpus2.json | 275d02f0af9cff691b0441568b4a9b02f19b70649dc1c51bb45ff8f9c697211c | 47534 |
| synthesis_containment.json | 34a900f06900f2027be8ad4e8fd76345407e185e06d0f4d2fe765785028554d0 | 17842 |
