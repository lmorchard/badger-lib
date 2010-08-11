Feature: Sample

  Scenario Outline: Naughty Step
    Given this step <Might Work>
    
    Examples:
    | Might Work             |
    | works                  |
    | does something naughty |
    | works                  |

  Scenario: Success
    Given this step works
    