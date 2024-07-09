# FEAS
FEAS is an automated theorem proving (ATP) agent specifically designed for solving functional equation problems within the Lean theorem prover environment. It builds upon the foundational work of the COPRA project (https://github.com/trishullab/copra) but is tailored exclusively for Lean, focusing on specialized techniques relevant to this domain.

## Setup Instructions
The setup for FEAS follows the same procedure as the COPRA project, tailored for Lean. Below are the relevant setup steps from the COPRA README, adapted for FEAS:

1. **Create and Activate a Miniconda Environment:**
   - Set up a `Miniconda` environment and activate it.

2. **Project Setup:**
   - Navigate to the project's root directory and execute the setup script: `./src/scripts/setup.sh`.
   Note: The `setup.sh` script includes some configurations for Coq and Isabelle which are not needed for FEAS.

3. **Configure Environment Variables for Lean:**
   - Add the following line to your `.bashrc` file:
     ```
     export PATH="/home/$USER/.elan/bin:$PATH"
     ```

4. **API Key Configuration:**
   - Create a file named `.secrets/openai_key.json` in the project root directory containing your OpenAI API key to run GPT models:
     ```json
     {
       "organization": "<your-organization-id>",
       "api_key": "<your-api-key>"
     }
     ```
   - Create a file named `.secrets/google_key.json` in the project root directory containing your Google Cloud API key to run Gemini, Claude and token count (for all models except GPTs):
     ```json
     {
       "api_key": "<your-api-key>"
     }
     ```
   - Create a file named `.secrets/llama_key.json` in the project root directory containing your Replicate API key:
     ```json
     {
       "api_key": "<your-api-key>"
     }
     ```


5. **FunEq dataset Lean Project Configuration:**
   - Run the following commands in `data/benchmarks/FunEq` directory:
     ```
     leanpkg configure
     leanproject get-mathlib-cache
     leanproject build
     ```

## Running FEAS Experiments
To run FEAS experiments, execute `src/main/eval_benchmark.py` with the specified parameters:

- Set `prompt_settings` according to the desired agent:
  - `lean_few_shot` for few-shot
  - `lean_dfs` for COPRA agent
  - `lean_dfs_block` for FEAS agent
  - `lean_dfs_block_strategy` for FEAS agent with heuristics

- Set `eval_settings` based on the desired LLM and agent:
  - For few-shot agent:
    - `n_4_few_gpt4_turbo` for GPT4 Turbo
    - `n_4_few_gemini` for Gemini1.5 Pro
    - `n_4_few_claude` for Claude3.5 Sonnet
    - `n_4_few_llama` for Llama3 70b 
  - For all other agents:
    - `n_60_dfs_gpt4_128k` for GPT4 Turbo
    - `n_60_dfs_gemini_pro` for Gemini1.5 Pro
    - `n_60_dfs_claude` for Claude3.5 Sonnet
    - `n_60_dfs_llama` for Llama3 70b

- Set `benchmark` based on the problem category of FunEq:
  - `simple_funeq` for simple problems
  - `intermediate_funeq` for intermediate-level problems
  - `imo_a1_funeq` for IMO shortlisted A1 problems
  - `imo_funeq` for other IMO shortlisted problems
  - `funeq` for running all problems of FunEq
