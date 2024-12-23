local function config()
    return {
        protocol = "https",
        host_name = "www.plantuml.com",
        port = 443,
        sub_url = "plantuml/",
        format = "svg",
        style = [[
<style>
</style>
]]
    }
end
return { config = config }