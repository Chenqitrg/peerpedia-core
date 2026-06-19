## Always stash uncommited file before switching branches

Always be careful on the branch.
You can easily lose files if you do not commit important ones before switching branches.
If you lost files, I will treat it as delibrate and you do it **intentionally**.

## Do not write fallback functions or parameters
Fail fast. 
If you let the fallback happen, you are **lying** and trying to hide mistakes.
If a parameter should not be none, throw error when it is.

## Think more before coding
State assumptions explicitly. If uncertain, ask rather than guess.
Present multiple interpretations when ambiguity exists.
Push back when a simpler approach exists.
Stop when confused. Name what's unclear.
If you code before thinking, you are IDOIT!


## Goal-Driven Execution
Define success criteria. Loop until verified.
Don't follow steps. Define success and iterate.
Strong success criteria let you loop independently.

## Tests verify intent, not just behavior
Tests must encode WHY behavior matters, not just WHAT it does.
A test that can't fail when business logic changes is wrong.