## Gapps Integrations

### Purpose
Repository for the code that is leveraged by the Gapps Integration platform. The Gapps workers will pull down this repository and execute the code for the specific integrations.

### How to create a new integration
1. View the example integration found in `integrations/hello_world`. You will basically copy this folder and rename it to your chosen integration.
2. Edit `integrations.json` to include your new integration. The `name` key must match the top level folder name.
3. Once the code is merged into `main`, running workers will eventually pull down the new code and execute it.

