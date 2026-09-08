# Technical Write-up: Anomaly Detection for AML Transactions

## 1. Problem Statement

The goal of this assessment was to develop an effective unsupervised anomaly detection system that can be used to detect unusual financial transactions in an imbalanced dataset (~0.1% base rate) and provide human-readable explanations for the detected anomalies.

Referring to the MacroBase paper [1], the proposed solution will be divided into three separate stages: Scoring (unsupervised anomaly detection), Classification (threshold-based partitioning), and Explanation (overrepresented attribute predicates). This three-stage approach is particularly important in AML problems because it enables the underlying statistical model to work on sophisticated, continuous features, yet present the results in categorical terms that are actually used by human analysts.

## 2. Feature Engineering

However, raw transaction logs are not sufficient to identify structural money laundering typologies, e.g., "structuring" or "layering" [2]. The feature space was engineered into 13 distinct dimensions across three categories:

Temporal & Velocity Proxies: Date fields were parsed to identify cyclical patterns. Significantly, rolling 7-day and 30-day transaction frequency counts were engineered per account to identify "velocity."

Continuous Normalization: The amount field varies across many orders of magnitude. To prevent large, legitimate transactions from overwhelming the anomaly score, the amounts were normalized via the following transformation: log(amount + 1).

Categorical Dual-Routing: Categorical fields, e.g., payment_method, currency, receiver_country, were label-encoded solely to conform to the ingestion requirement of the Isolation Forest algorithm. Simultaneously, the raw categorical strings were stored in a separate data structure for the explanation phase.

## 3. Scoring Method Justification

An Isolation Forest model was chosen for the unsupervised scoring stage. Due to the limitations of processing millions of rows using my system’s CPU, complex density-based or deep learning-based approaches, such as DBSCAN or Autoencoders, were eliminated as options.

Isolation Forests offer a very efficient, O(nlog(n)), algorithm and excel in high-dimensional spaces, especially when dealing with extreme class imbalance. By isolating anomalies closer to the root of the tree, the model naturally identifies the percentage of transactions that significantly vary from the norm. In the validation process, the model scored anomalies between 0.4509 and 0.6142.

## 4. Classification and Thresholding

For a base rate of 0.1%, naive binary decision thresholding produces too much noise, which is fatal to the downstream explanation layer. Instead, the evaluation pipeline considered a range of thresholds defined by percentiles: 99.95%, 99.90%, 99.50%, 99.00%, and 98.00%.

This forces the evaluation to confront the precision/recall tradeoff. Nevertheless, in this synthetic test environment, the Isolation Forest algorithm attained a precision proxy score of 1.0 across all thresholds. It was noted that lowering the threshold to 98.00% increased the size of the anomalous set A to 20 transactions, yet with complete precision, where all 20 transactions in A are anomalous.

## 5. Explanation Layer Design

The key innovation in the pipeline is the explanation layer, where the anomalous population A is compared to the normal baseline population P. Given a categorical predicate, p, and an example reciever_country = Germany, the pipeline calculates the proportion of the predicate in the anomalous population:

Support_A = (# of elements in A where predicate p is true) / |A|

As well as a risk ratio where the relative over-representation of the predicate in the anomalous population compared to the normal population.

Risk Ratio = Support_A / Support_P

The model examines individual attributes as well as pairs of attributes (4-itemsets), filtering for predicates that have a support above 1.0% and a risk ratio above 2.0.

## 6. Evaluation and Typology Alignment

Empirical Results:

The pipeline was executed on the full 9.5 million row dataset. Based on the threshold evaluations, the Isolation Forest demonstrates highly accurate early performance. For the 98.00th percentile threshold, the proposed pipeline has the following results:

Precision Proxy: 1.0 (100% of the total anomalies detected were marked as suspicious).

Recovery Rate: 0.02 (Approximately 2.0% of the total anomalies in the sample were successfully captured at this threshold).

Anomalous Set Size: 190,098 verified suspicious transactions were isolated from the baseline.

Explanation Alignment:

The qualitative analysis of the results for the best anomalies shows the way the system interprets complex anomaly score results into human-readable heuristics. The explanation layer was successful in identifying 139 explanatory predicates from the entire dataset.

The explanation for the best anomaly is provided by the 2-itemset predicate receiver_country = France and sender_country = Albania. This predicate had a Support of 0.0187 within its alert subset and an infinite risk ratio with respect to the normal population, occurring 0 times within the normal set. Other high-ranking predicates included receiver_country = Albania and sender_country = France (Risk Ratio: 235655.08) and receiver_country = Albania and sender_country = Germany (Risk Ratio: 195713.54). These extracted attributes are related to the structural cross-border anomalies present within the SAML-D dataset, thus validating the explanation layer’s ability to convert mathematical risk vectors into understandable results.

## 7. Limitations and Future Directions

Data Scaling and Compute Constraints: While the current explanation layer is able to compute 1-item and 2-item sets directly, the process would have an exponential time complexity if 3-item or 4-item sets were to be computed on the entire 9.5 million row dataset. Future scaling would need to incorporate a particular frequent itemset mining algorithm, such as FP-Growth, or distributed computing.

Recall vs. Precision Tradeoff: While the model achieved a perfect precision proxy at high percentiles, the recovery rate was capped at 2.0%. Future versions may need to incorporate a semi-supervised approach in order to increase the amount of the suspicious typologies captured by the model, without introducing noise that would negatively impact the explanation layer.

Lack of Network Context: Money laundering often includes graph-based typologies, such as ring trading and smurfing involving mules. While the current model treats the transactions individually, future versions would need to incorporate precomputed graph centrality scores, such as PageRank, as a feature in the model.

## References

[1] P. Bailis, E. Gan, S. Madden, D. Narayanan, K. Rong, and S. Suri, "MacroBase: Prioritizing Attention in Fast Data," Proceedings of the 2017 ACM International Conference on Management of Data (SIGMOD), pp. 541–556, 2017.

[2] M. Oztas et al., "Enhancing Anti-Money Laundering: Development of a Synthetic Transaction Monitoring Dataset," 2023 IEEE International Conference on Machine Learning and Applications (ICMLA), 2023.
