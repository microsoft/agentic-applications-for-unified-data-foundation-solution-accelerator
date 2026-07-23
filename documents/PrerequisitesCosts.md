## Prerequisites & Costs

To deploy this solution accelerator, ensure you have:

- An [Azure subscription](https://azure.microsoft.com/free/) with permissions to create **resource groups, resources, app registrations, and assign roles at the resource group level**
- **Contributor** role at the subscription level and **Role Based Access Control** role on the subscription and/or resource group level
<!-- - A minimum **F2 Fabric capacity** — [Set up Fabric Capacity](https://learn.microsoft.com/en-us/fabric/admin/capacity-settings?tabs=fabric-capacity#create-a-new-capacity) -->

Follow the steps in [Azure Account Set Up](./documents/AzureAccountSetUp.md) for detailed account configuration.

**Regional availability:** East US, East US2, Australia East, UK South, France Central — [Check all regions](https://azure.microsoft.com/en-us/explore/global-infrastructure/products-by-region/?products=all&regions=all)

**Cost estimation:**
- [Azure Pricing Calculator](https://azure.microsoft.com/en-us/pricing/calculator)
- [Fabric Capacity Estimator](https://www.microsoft.com/en-us/microsoft-fabric/capacity-estimator)
- [Sample Pricing Sheet](https://azure.com/e/708895d4fc4449b1826016fad8a83fe0)

_Note: This is not meant to outline all costs as selected SKUs, scaled use, customizations, and integrations into your own tenant can affect the total consumption of this sample solution. The sample pricing sheet is meant to give you a starting point to customize the estimate for your specific needs._

<details>
<summary>View resource pricing details</summary>

| Product | Description | Tier / Expected Usage Notes | Cost |
|---|---|---|---|
| [Microsoft Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry) | Used to orchestrate and build AI workflows that combine Azure AI services. | Free Tier | [Pricing](https://azure.microsoft.com/pricing/details/ai-studio/) |
| [Azure AI Services (OpenAI)](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/overview) | Enables language understanding and chat capabilities using GPT models. | S0 Tier; pricing depends on token volume and model used (e.g., GPT-4o-mini). | [Pricing](https://azure.microsoft.com/pricing/details/cognitive-services/) |
| [Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/overview) | Hosts microservices and APIs powering the front-end and backend orchestration. | Consumption plan with 0.5 vCPU, 1GiB memory; includes a free usage tier. | [Pricing](https://azure.microsoft.com/pricing/details/container-apps/) |
| [Azure Container Registry](https://learn.microsoft.com/en-us/azure/container-registry/container-registry-intro) | Stores and serves container images used by Azure Container Apps. | Basic Tier; fixed daily cost per registry. | [Pricing](https://azure.microsoft.com/pricing/details/container-registry/) |
| [Azure Monitor / Log Analytics](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/log-analytics-overview) | Collects and analyzes telemetry and logs from services and containers. | Pay-as-you-go; charges based on data ingestion volume. | [Pricing](https://azure.microsoft.com/pricing/details/monitor/) |
| [SQL Database in Fabric](https://learn.microsoft.com/en-us/fabric/fundamentals/microsoft-fabric-overview) | Stores structured data including insights, metadata, and chat history. | F2 capacity; fixed monthly cost per capacity. | [Pricing](https://azure.microsoft.com/en-us/pricing/details/microsoft-fabric/) |

</details>

> ⚠️ **Important:** To avoid unnecessary costs, remember to take down your app if it's no longer in use, either by deleting the resource group in the Portal or running `azd down`.
