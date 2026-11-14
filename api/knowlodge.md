Company Knowledge Source: Fabrikam Mobility Ltd

Who they are
Fabrikam Mobility Ltd is a company based in St Julian’s, Malta. It works in the mobility (transport technology) space.

What they are building
A travel-assistance application for visitors and residents in Malta. The app helps people choose how to get from one place to another, for example from the airport, ferry or cruise terminals to hotels and attractions.

Who their users are

Tourists visiting Malta. Malta had 4,022,310 inbound tourists in 2025, according to the National Statistics Office (NSO).
Residents of Malta.

Most users need to travel quickly and at a fair price.

What the company wants
Fabrikam wants to help users choose transport without tying the app to one provider. This is called being provider-independent (not locked in to a single vendor).

Problems the company faces (from their RFP, or Request for Proposal)

Transport providers use different APIs, login methods and response formats.
Some commercial providers do not give open public API access, so approved sandboxes (safe test environments) or mock services (fake test versions) may be needed.
One provider going down must not break the whole app.
An AI model must never invent prices, availability or journey times. These must come from real provider data.
New providers must be easy to add without a major rewrite (extensibility).

What the company values

Trustworthy, explainable recommendations (Responsible AI).
Privacy and data protection under EU rules (GDPR), since Malta is in the EU.
Security and reliability.
Low cost. The first version (the MVP, or Minimum Viable Product) must run at zero cost.
No scraping or reverse-engineering of other companies’ apps.

Related details

RFP reference: MMAUG-AIDB-RFP-004, “Fabrikam Mobility Taxi Recommender”.
Cloud platform used for hosting: Microsoft Azure (resource group: rg_fabrikam_ltd, North Europe region).
Provider names in the project (Bolt, Uber, eCabs) are trademarks of other companies. They are only imitated in test form and are not partners.