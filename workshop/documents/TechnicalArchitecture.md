## Technical Architecture

This section outlines the components and interactions that powers the unified data analysis platform. The architecture ingests customer information, product details and transaction history and surfaces insights via an interactive web experience.

#### Option 1: Architecture with Microsoft Fabric and Microsoft Copilot Studio:

![image](./Images/ReadMe/solution-architecture-cps.png)

### Customer / product / transaction details
SQL scripts for the customer, product and transaction details are the primary input into the system. These tables are uploaded and stored for downstream insight generation.

### SQL Database in Fabric  
Stores uploaded customer information, product details and transaction history tables. Serves as the primary knowledge source to surface insights in the Fabric Data Agent.

### Fabric Data Agent 
Provides large language model (LLM) capabilities to support naltural language querying. 

### Microsoft Copilot Studio
Fabric Data Agent is connected to an agent in Microsoft Copilot Studio and surfaced as a channel in Microsoft Teams. 

### Microsoft Teams
Users can explore call insights, visualize trends, ask questions in natural language, directly inside Microsoft Teams. 


#### Option 2: Architecture with Microsoft Fabric and Microsoft Foundry:

![image](./Images/ReadMe/solution-architecture.png)

### Customer / product / transaction details
SQL scripts for the customer, product and transaction details are the primary input into the system. These tables are uploaded and stored for downstream insight generation.

### SQL Database in Fabric  
Stores uploaded customer information, product details and transaction history tables. Serves as the primary knowledge source to surface insights in the web application. And persists chat history and session context for the web interface. Enables retrieval of past interactions.

### Microsoft Foundry
Provides large language model (LLM) capabilities to support natural language querying.

### Agent Framework  
Handles orchestration and intelligent function/tool calling for contextualized responses and multi-step reasoning over retrieved data.

### App Service  
Hosts the web application and API layer that interfaces with the AI services and storage layers. Manages user sessions and handles REST calls.

### Container Registry  
Stores containerized deployments for use in the hosting environment.

### Web Front-End  
An interactive UI where users can explore call insights, visualize trends, ask questions in natural language, and generate charts. Connects directly to SQL Database in Fabric and App Services for real-time interaction.