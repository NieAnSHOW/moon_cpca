///|
pub enum Level {
  Province
  City
  Area
}

///|
pub struct Rec {
  adcode : String
  name : String
  level : Level
}

///|
pub let adcodes : Array[Rec] = [
  { adcode: "500233000000", name: "忠县", level: Area },
]
