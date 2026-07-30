# DHNRBC
Study of the optimal design of a district heating network for the centre of Brussels, taking into account the constraints associated with the renovation of listed buildings.

## Demand modelling

To collect and store WFS data locally in the [Data](Data/) folder, run the appropriate scripts located in the [API](Demand/API/) subdirectory. Note that no data is tracked by Git.

## PCST

Run the appropriate scripts in the [Optim](Optim/) folder to solve the Prize-Collecting Steiner Tree Problem.

## Requirements

The Python environment for this project can be created from the `environment.yaml` file by running the following command in the Anaconda Prompt:

```
conda env create -f "<path-to-environment.yaml>"
```

To update an existing environment instead, use:

```
conda env update -f "<path-to-environment.yaml>"
```