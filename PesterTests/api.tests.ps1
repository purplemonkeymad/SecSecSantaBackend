[CmdletBinding()]
param (
    [Parameter()]
    [uri]
    $APIEndpoint = 'http://localhost:5000'
)
$DefParams = @{
    UseBasicParsing = $true
    'ContentType' = 'application/json'
}

Import-Module pester

$persistantVariables = @{}

Describe "/new" {
    Context "Data Errors" {
        It "No post data errors" {
            $r = Invoke-RestMethod "$APIEndpoint/new" -Method Post
            $r.status | Should -Be "error"
        }
        It "Empty data errors" {
            $r = Invoke-RestMethod "$APIEndpoint/new" -Method Post -Body "{}"
            $r.status | Should -Be "error"
        }
    }
    Context "New Test Game" {
        It "Creates a new game" {
            $persistantVariables.NewGame = Invoke-RestMethod "$APIEndpoint/new" -Method Post -Body '{"name":"Pester Testing Game"}'
            $persistantVariables.NewGame | Should -Not -BeNullOrEmpty
        }
        It "Was a success" {
            $persistantVariables.NewGame.status | Should -Be "ok"
        }
        It "As a matching name" {
            $persistantVariables.NewGame.Name | Should -Be "Pester Testing Game"
        }
        It "Has a non-empty id" {
            $persistantVariables.NewGame.pubkey | Should -not -BeNullOrEmpty
        }
        It "Has a non empty secret" {
            $persistantVariables.NewGame.privkey | Should -not -BeNullOrEmpty
        }
    }
}
Describe "/game read data" {
    Context "Data errors" {
        It "No param errors" {
            $r = Invoke-RestMethod "$APIEndpoint/game" -Method Get
            $r.status | Should -Be "error"
        }
        It "Empty code errors" {
            $r = Invoke-RestMethod "$APIEndpoint/game?code=" -Method Get
            $r.status | Should -Be "error"
        }
        It "Missing code errors" {
            $r = Invoke-RestMethod "$APIEndpoint/game?code=TestShould%20Not%20Exist" -Method Get
            $r.status | Should -Be "error"
        }
    }
    Context "New Game Values" {
        It "Gets the new game" {
            $persistantVariables.GetGame = Invoke-RestMethod "$APIEndpoint/game?code=$($persistantVariables.NewGame.pubkey)" -Method get
            $persistantVariables.GetGame | Should -Not -BeNullOrEmpty
        }
        It "Was a success" {
            $persistantVariables.GetGame.status | Should -Be "ok"
        }
        It "Should have a name" {
            $persistantVariables.GetGame.name | Should -not -BeNullOrEmpty
        }
        It "Should match the test Name" {
            $persistantVariables.GetGame.name | Should -Be "Pester Testing Game"
        }
        It "Should return a valid state" {
            $persistantVariables.GetGame.state | Should -BeIn 1,2,3
        }
    }
}