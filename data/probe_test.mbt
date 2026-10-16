test "probe: data package compiles and adcodes loads" {
  inspect(adcodes.length(), content="1")
  inspect(adcodes[0].adcode, content="500233000000")
  inspect(adcodes[0].name, content="忠县")
}
