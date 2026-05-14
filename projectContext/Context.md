The desired system will be developed with these considerations :
- the system should contain a logging system that logs each component seperately in a log file or text file 
- Always handle edge cases while developing each component or each feature 
- Do not use any emojies STRICLTY
- DO NOT USE ANY HARD CODED VALUES
- Always implement production ready code
- Branch stable-testing should be for stable versions only
- when implementing a new feature, ensure its compatibilty with what was already implemented.


The tech stack to be used is :
- React for frontend 
- FastAPI for Backend
- PostgreSQL for Database
- Python 3.11.0 
- PaddleOCR 3.x 


Always commit every change sperately (Split of concerns)
Follow the below GIT conventions :
- Feat (Feature name): Feature description + #Github issue ID : if not provided request it
- Chore (name) : for medium changes 
- test : for tests
- Perf : for performances commits
- Docs : for documentation commits


ALWAYS document and summarize every implemented and tested feature under /docs/feature/featureName/ - if the folder is not created or found, create it.

ALWAYS provide suggestions to implement new feature with pros and cons and estimation of effort.

ALWAYS run unit tests after each implemented feature and store the results under docs/tests/testForFeatureX

When investigating a bug, ALWAYS store the bug logs under docs/bugs/bugX

when implementing a new feature, refer to the context and docs under /projectContext 



