# Delete resources

Delete your Azure resources when you're done to manage costs.

## Delete Azure Resources

```bash
azd down
```

Confirm when prompted:

```
? Total resources to delete: 8, are you sure? (y/N) y
```

## Verify Deletion

1. Go to [Azure Portal](https://portal.azure.com/)
2. Check **Resource groups**
3. Confirm your lab resource group is deleted

!!! warning "Important"
    Always run cleanup to avoid ongoing charges!

## Clean Up Fabric (Optional)

If you created Fabric artifacts and want to remove them:

1. Go to [Microsoft Fabric](https://app.fabric.microsoft.com/)
2. Open your workspace
3. Delete the Lakehouse and Warehouse created for this workshop

## Clean Up Local Files (Optional)

Remove generated data folders:

=== "Windows PowerShell"

    ```powershell
    Remove-Item -Recurse -Force data\*_*
    ```

=== "macOS/Linux"

    ```bash
    rm -rf data/*_*/
    ```

---

[Next steps →](next-steps.md)
