# Shared FitStart catalog

Recipes and exercise instructions are global read-only catalogue records imported from the V1 application source. User-specific favorites remain separate records per account.

Seed/update using:

    python manage.py import_v1_catalog

The import reads `catalogs/v1-catalog.json` at the V2 backend root and is idempotent: keys are diet/menu/slot for recipes, V1 exercise IDs for exercises, and mode/level/routine-index for routines.

The imported V1 dataset contains 160 recipes and 80 distinct exercise definitions in 16 routines.
