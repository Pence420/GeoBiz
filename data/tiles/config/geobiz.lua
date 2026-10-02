-- GeoBiz deliberately copies only attributes needed by the committed local style.
function init_function(name, is_first)
end

function exit_function()
end

local function set_name()
  local name = Find("name")
  if name ~= "" then Attribute("name", name) end
end

function node_function()
  local place = Find("place")
  if place ~= "" then
    Layer("place", false)
    Attribute("class", place)
    set_name()
  end
  local amenity = Find("amenity")
  local shop = Find("shop")
  if amenity ~= "" or shop ~= "" then
    Layer("poi", false)
    Attribute("class", amenity ~= "" and amenity or "shop")
    if shop ~= "" then Attribute("subclass", shop) end
    set_name()
  end
end

function way_function()
  local natural = Find("natural")
  local waterway = Find("waterway")
  local landuse = Find("landuse")
  local building = Find("building")
  local highway = Find("highway")
  local boundary = Find("boundary")

  if natural == "water" or Find("water") ~= "" then
    Layer("water", true)
    Attribute("class", natural ~= "" and natural or "water")
  elseif waterway ~= "" then
    Layer("waterway", false)
    Attribute("class", waterway)
    set_name()
  end
  if landuse ~= "" or Find("leisure") == "park" then
    Layer("landuse", true)
    Attribute("class", landuse ~= "" and landuse or "park")
  end
  if building ~= "" then
    Layer("building", true)
    Attribute("class", building)
  end
  if highway ~= "" then
    Layer("transportation", false)
    Attribute("class", highway)
    local ref = Find("ref")
    if ref ~= "" then Attribute("ref", ref) end
    set_name()
  end
  if boundary == "administrative" then
    Layer("boundary", false)
    Attribute("class", "administrative")
    local admin_level = Find("admin_level")
    if admin_level ~= "" then Attribute("admin_level", admin_level) end
    set_name()
  end
end

function relation_scan_function()
  if Find("type") == "multipolygon" or Find("boundary") == "administrative" then
    Accept()
  end
end
