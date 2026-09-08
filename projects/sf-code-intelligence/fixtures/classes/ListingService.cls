/**
 * Minimal fixture for explicit SOQL → SObject edges: Listing__c and Broker__c.
 */
public with sharing class ListingService {
    @AuraEnabled(cacheable=true)
    public static List<Listing__c> getActiveListings() {
        return [
            SELECT Id, Name, Price__c, Broker__c
            FROM Listing__c
            WHERE Price__c != NULL
            ORDER BY Price__c
            LIMIT 50
        ];
    }

    public static Integer countBrokers() {
        return [SELECT COUNT() FROM Broker__c];
    }
}
