import DX

#
# Open channel to DX
#
wallet = DX.wallet.load("wallet_file.json", "password")
channel = DX.channel.open(wallet, node="https://api-alpha.dx.network", deposit=50)
channel.print_state();

#
# Tech Industry search (https://docs.dx.network/#search-organizations)
#
result = channel.query("techindustry/organizations", {
    "city": "London",
    "market": "<urn:dx:tech-industry:market/finance>",
    "teamsize": "100",
    "has_revenue": "true"
}, metadata=False)
print(result)
channel.print_balance()

#
# Tech Industry fetch (https://docs.dx.network/#fetch-an-organization)
#
result = channel.query("techindustry/organizations/c2eb0645-1d77-4bbb-9f29-033f582ed730", metadata=True)
print(result)
channel.print_balance()

#
# Semantic search (https://docs.dx.network/#search-by-semantic-query)
#
result = channel.query("semantic/search", {"query": """
    SELECT $org $name WHERE {
        $org a dx:Organization ;
             dx:hasMarket <urn:dx:tech-industry:market/ai> ;
             dx:hasHeadquarter $addr ;
             dx:hasUserType $user_type ;
             dx:entityName $name .

        $addr dx:addressCity "London" ;
              dx:hasCountry <urn:dx:tech-industry:country/gb> .

        FILTER (
            $user_type IN (
                <urn:dx:tech-industry:user-type/b2b>,
                <urn:dx:tech-industry:user-type/b2g>
            )
        )
    }
    PAGE 1 SIZE 3
"""})
print(result)
channel.print_balance()

#
# Close channel to DX
#
channel.settle()

channel.print_state();
