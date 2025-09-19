## Technical Architecture

This section outlines the components and interactions that powers the unified data analysis platform. The architecture ingests customer information, product details and order history and surfaces insights via an interactive web experience.

![image](./Images/ReadMe/solution-architecture.png)

### Customer / product / order details
SQL scripts for the customer, product and order details are the primary input into the system. These tables are uploaded and stored for downstream insight generation.

### SQL Database in Fabric  
Stores uploaded customer information, product details and order history tables. Serves as the primary knowledge source to surface insights in the web application. And persists chat history and session context for the web interface. Enables retrieval of past interactions.

### Azure OpenAI Service  
Provides large language model (LLM) capabilities to support natural language querying.

### Semantic Kernel  
Handles orchestration and intelligent function calling for contextualized responses and multi-step reasoning over retrieved data.

### App Service  
Hosts the web application and API layer that interfaces with the AI services and storage layers. Manages user sessions and handles REST calls.

### Container Registry  
Stores containerized deployments for use in the hosting environment.

### Web Front-End  
An interactive UI where users can explore call insights, visualize trends, ask questions in natural language, and generate charts. Connects directly to SQL Database in Fabric and App Services for real-time interaction.