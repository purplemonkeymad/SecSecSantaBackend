#requires -module pester

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

Write-Host "testing Game: $(Out-string -InputObject $persistantVariables.NewGame)"

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
            $persistantVariables.GetGame.state | Should -BeIn 0,1,2
        }
    }
}

Describe "/user on test game" {
    Context "error for new" {
        It "No param errors" {
            $r = Invoke-RestMethod "$APIEndpoint/user" -Method Post
            $r.status | Should -Be "error"
        }
        It "empty post values" {
            $r = Invoke-RestMethod "$APIEndpoint/user" -Method Post -Body '{}'
            $r.status | Should -Be "error"
        }
        It "missing Name" {
            $r = Invoke-RestMethod "$APIEndpoint/user" -Method Post -Body (@{code=$persistantVariables.NewGame.pubkey} | ConvertTo-Json)
            $r.status | Should -Be "error"
        }
        It "missing code" {
            $r = Invoke-RestMethod "$APIEndpoint/user" -Method Post -Body (@{name = "Error User"} | ConvertTo-Json)
            $r.status | Should -Be "error"
        }
    }
    Context "Registration" {
        It "Registers User <number>" -TestCases (1..4 | % { @{ number = $_ }}) {
            Param($number)
            $r = Invoke-RestMethod "$APIEndpoint/user" -Method Post -Body (@{code=$persistantVariables.NewGame.pubkey;name = "Test User $number"} | ConvertTo-Json)
            $r.status | Should -Be "ok"
        }
    }
}

Describe "/idea on game" {
    Context "error for new" {
        It "No param errors" {
            $r = Invoke-RestMethod "$APIEndpoint/idea" -Method Post
            $r.status | Should -Be "error"
        }
        It "empty post values" {
            $r = Invoke-RestMethod "$APIEndpoint/idea" -Method Post -Body '{}'
            $r.status | Should -Be "error"
        }
        It "missing idea" {
            $r = Invoke-RestMethod "$APIEndpoint/idea" -Method Post -Body (@{code=$persistantVariables.NewGame.pubkey} | ConvertTo-Json)
            $r.status | Should -Be "error"
        }
        It "missing code" {
            $r = Invoke-RestMethod "$APIEndpoint/idea" -Method Post -Body (@{idea = "Error Idea"} | ConvertTo-Json)
            $r.status | Should -Be "error"
        }
    }
    Context "Submission" {
        It "Adds an idea <number>" -TestCases (1..8 | % { @{ number = $_ }}) {
            param($number)
            $r = Invoke-RestMethod "$APIEndpoint/idea" -Method Post -Body (@{code=$persistantVariables.NewGame.pubkey;idea = "Test Idea $number"} | ConvertTo-Json)
            $r.status | Should -Be "ok"
        }
    }
}

Describe "/game state changes" {
    Context "post errors" {
        It "No param errors" {
            $r = Invoke-RestMethod "$APIEndpoint/game" -Method Post
            $r.status | Should -Be "error"
        }
        It "empty post values" {
            $r = Invoke-RestMethod "$APIEndpoint/game" -Method Post -Body '{}'
            $r.status | Should -Be "error"
        }
        It "missing secret" {
            $r = Invoke-RestMethod "$APIEndpoint/game" -Method Post -Body (@{code=$persistantVariables.NewGame.pubkey} | ConvertTo-Json)
            $r.status | Should -Be "error"
        }
        It "missing code" {
            $r = Invoke-RestMethod "$APIEndpoint/game" -Method Post -Body (@{secret=$persistantVariables.NewGame.privkey} | ConvertTo-Json)
            $r.status | Should -Be "error"
        }
    }
    Context "state errors" {
        It "missing secret" {
            $r = Invoke-RestMethod "$APIEndpoint/game" -Method Post -Body (@{code=$persistantVariables.NewGame.pubkey;state=0} | ConvertTo-Json)
            $r.status | Should -Be "error"
        }
        It "missing code" {
            $r = Invoke-RestMethod "$APIEndpoint/game" -Method Post -Body (@{secret=$persistantVariables.NewGame.privkey;state=0} | ConvertTo-Json)
            $r.status | Should -Be "error"
        }
        It "Same state" {
            $r = Invoke-RestMethod "$APIEndpoint/game" -Method Post -Body (@{
                secret=$persistantVariables.NewGame.privkey
                code=$persistantVariables.NewGame.pubkey
                state=0
            } | ConvertTo-Json)
            $r.status | Should -Be "error"
        }
    }
    Context "run game" {
        It "updates state" {
            $r = Invoke-RestMethod "$APIEndpoint/game" -Method Post -Body (@{
                secret=$persistantVariables.NewGame.privkey
                code=$persistantVariables.NewGame.pubkey
                state=1
            } | ConvertTo-Json)
            $r.status | Should -Be "ok"
        }
    }
}