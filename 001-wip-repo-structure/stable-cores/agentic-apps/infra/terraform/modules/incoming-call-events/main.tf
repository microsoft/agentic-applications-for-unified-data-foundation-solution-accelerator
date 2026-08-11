resource "azurerm_eventgrid_system_topic" "main" {
  name                   = var.name
  resource_group_name    = var.resource_group_name
  location               = "global"
  source_arm_resource_id = var.communication_service_id
  topic_type             = "Microsoft.Communication.CommunicationServices"
  tags                   = var.tags
}

resource "azurerm_eventgrid_event_subscription" "incoming_call" {
  count = var.webhook_endpoint == null ? 0 : 1

  name  = "${var.name}-incoming-call"
  scope = var.communication_service_id

  webhook_endpoint {
    url                               = var.webhook_endpoint
    max_events_per_batch              = 1
    preferred_batch_size_in_kilobytes = 64
  }

  included_event_types = ["Microsoft.Communication.IncomingCall"]

  retry_policy {
    max_delivery_attempts = 30
    event_time_to_live    = 1440
  }

  depends_on = [azurerm_eventgrid_system_topic.main]
}
