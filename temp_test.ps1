$headers = @{
    "Content-Type"   = "application/json"
    "X-Client-Token" = "92faa8bc61a57fa988412c47417a0fb08843c9e684769062b3cf1abca2d074ff"
}
$body = @{
    client_id = "443f5716-27d3-463a-9397-33a666f5ad88"
    message   = "Based on our philosophy, what's our approach to posterior crowns?"
} | ConvertTo-Json

Invoke-WebRequest -Uri "http://chatbot-api-alb-1718711412.us-west-2.elb.amazonaws.com/api/clinical/chat" `
                  -Method POST `
                  -Headers $headers `
                  -Body $body `
                  -UseBasicParsing | Select-Object -ExpandProperty Content
