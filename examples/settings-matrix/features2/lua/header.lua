function envoy_on_request(request_handle)
  local path = request_handle:headers():get(":path")
  request_handle:headers():add("x-epl-filter", "1")
end

function envoy_on_response(response_handle)
  response_handle:headers():add("x-epl-filter", "1")
end
