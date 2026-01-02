"""
Scanning Optimization Script
Analyzes feedback data and generates insights for model improvement

Run this periodically (weekly/monthly) to review scanning accuracy
and identify areas for prompt/model improvement
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List
import json

from app.core.database import get_db_client


class ScanningOptimizer:
    """Analyze scanning performance and generate improvement recommendations"""
    
    def __init__(self):
        self.db = get_db_client()
    
    async def generate_report(self, days: int = 30) -> Dict:
        """
        Generate comprehensive scanning performance report
        
        Args:
            days: Number of days to analyze (default 30)
            
        Returns:
            Report dict with metrics, common errors, recommendations
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        print(f"\n{'='*60}")
        print(f"SAVO Scanning Optimization Report")
        print(f"Period: Last {days} days ({cutoff_date.date()} to {datetime.utcnow().date()})")
        print(f"{'='*60}\n")
        
        # 1. Overall metrics
        print("1. OVERALL METRICS")
        print("-" * 60)
        metrics = await self._get_overall_metrics(cutoff_date)
        self._print_metrics(metrics)
        
        # 2. Common misidentifications
        print("\n\n2. COMMON MISIDENTIFICATIONS")
        print("-" * 60)
        errors = await self._get_common_errors(cutoff_date)
        self._print_errors(errors)
        
        # 3. Confidence analysis
        print("\n\n3. CONFIDENCE ANALYSIS")
        print("-" * 60)
        confidence_stats = await self._get_confidence_stats(cutoff_date)
        self._print_confidence_stats(confidence_stats)
        
        # 4. User feedback analysis
        print("\n\n4. USER FEEDBACK ANALYSIS")
        print("-" * 60)
        feedback_stats = await self._get_feedback_stats(cutoff_date)
        self._print_feedback_stats(feedback_stats)
        
        # 5. Recommendations
        print("\n\n5. RECOMMENDATIONS FOR IMPROVEMENT")
        print("-" * 60)
        recommendations = self._generate_recommendations(
            metrics, errors, confidence_stats, feedback_stats
        )
        self._print_recommendations(recommendations)
        
        # 6. Prompt improvements
        print("\n\n6. SUGGESTED PROMPT IMPROVEMENTS")
        print("-" * 60)
        prompt_suggestions = self._generate_prompt_improvements(errors)
        self._print_prompt_suggestions(prompt_suggestions)
        
        return {
            "period_days": days,
            "metrics": metrics,
            "errors": errors,
            "confidence_stats": confidence_stats,
            "feedback_stats": feedback_stats,
            "recommendations": recommendations,
            "prompt_suggestions": prompt_suggestions
        }
    
    async def _get_overall_metrics(self, cutoff_date: datetime) -> Dict:
        """Get high-level metrics"""
        
        # Total scans
        scans_result = await self.db.table("ingredient_scans") \
            .select("id", count="exact") \
            .gte("created_at", cutoff_date.isoformat()) \
            .execute()
        total_scans = scans_result.count or 0
        
        # Total detections
        detections_result = await self.db.table("detected_ingredients") \
            .select("id", count="exact") \
            .gte("created_at", cutoff_date.isoformat()) \
            .execute()
        total_detections = detections_result.count or 0
        
        # Confirmed/rejected breakdown
        status_result = await self.db.table("detected_ingredients") \
            .select("confirmation_status") \
            .gte("created_at", cutoff_date.isoformat()) \
            .execute()
        
        confirmed = sum(1 for r in status_result.data if r["confirmation_status"] == "confirmed")
        modified = sum(1 for r in status_result.data if r["confirmation_status"] == "modified")
        rejected = sum(1 for r in status_result.data if r["confirmation_status"] == "rejected")
        pending = sum(1 for r in status_result.data if r["confirmation_status"] == "pending")
        
        # Accuracy rate
        total_resolved = confirmed + modified + rejected
        accuracy_rate = (confirmed / total_resolved * 100) if total_resolved > 0 else 0
        
        # Average confidence
        confidence_result = await self.db.table("detected_ingredients") \
            .select("confidence") \
            .gte("created_at", cutoff_date.isoformat()) \
            .execute()
        
        confidences = [r["confidence"] for r in confidence_result.data]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        # Active users
        users_result = await self.db.table("ingredient_scans") \
            .select("user_id") \
            .gte("created_at", cutoff_date.isoformat()) \
            .execute()
        active_users = len(set(r["user_id"] for r in users_result.data))
        
        return {
            "total_scans": total_scans,
            "total_detections": total_detections,
            "confirmed": confirmed,
            "modified": modified,
            "rejected": rejected,
            "pending": pending,
            "accuracy_rate": accuracy_rate,
            "avg_confidence": avg_confidence,
            "active_users": active_users,
            "avg_detections_per_scan": total_detections / total_scans if total_scans > 0 else 0
        }
    
    async def _get_common_errors(self, cutoff_date: datetime, limit: int = 20) -> List[Dict]:
        """Get most common misidentifications"""
        
        corrections_result = await self.db.table("scan_corrections") \
            .select("*") \
            .gte("last_occurrence", cutoff_date.isoformat()) \
            .order("occurrence_count", desc=True) \
            .limit(limit) \
            .execute()
        
        return corrections_result.data
    
    async def _get_confidence_stats(self, cutoff_date: datetime) -> Dict:
        """Analyze confidence distribution and accuracy by confidence level"""
        
        detections_result = await self.db.table("detected_ingredients") \
            .select("confidence, confirmation_status") \
            .gte("created_at", cutoff_date.isoformat()) \
            .execute()
        
        high_conf = [d for d in detections_result.data if d["confidence"] >= 0.80]
        medium_conf = [d for d in detections_result.data if 0.50 <= d["confidence"] < 0.80]
        low_conf = [d for d in detections_result.data if d["confidence"] < 0.50]
        
        def calc_accuracy(items):
            resolved = [i for i in items if i["confirmation_status"] in ["confirmed", "modified", "rejected"]]
            if not resolved:
                return 0.0
            confirmed = sum(1 for i in resolved if i["confirmation_status"] == "confirmed")
            return confirmed / len(resolved) * 100
        
        return {
            "high_confidence": {
                "count": len(high_conf),
                "accuracy": calc_accuracy(high_conf)
            },
            "medium_confidence": {
                "count": len(medium_conf),
                "accuracy": calc_accuracy(medium_conf)
            },
            "low_confidence": {
                "count": len(low_conf),
                "accuracy": calc_accuracy(low_conf)
            }
        }
    
    async def _get_feedback_stats(self, cutoff_date: datetime) -> Dict:
        """Analyze user feedback"""
        
        feedback_result = await self.db.table("scan_feedback") \
            .select("*") \
            .gte("created_at", cutoff_date.isoformat()) \
            .execute()
        
        total_feedback = len(feedback_result.data)
        
        ratings = [f for f in feedback_result.data if f.get("overall_rating")]
        avg_rating = sum(f["overall_rating"] for f in ratings) / len(ratings) if ratings else 0
        
        accuracy_ratings = [f for f in feedback_result.data if f.get("accuracy_rating")]
        avg_accuracy_rating = sum(f["accuracy_rating"] for f in accuracy_ratings) / len(accuracy_ratings) if accuracy_ratings else 0
        
        corrections = [f for f in feedback_result.data if f["feedback_type"] == "correction"]
        false_positives = [f for f in feedback_result.data if f["feedback_type"] == "false_positive"]
        missing = [f for f in feedback_result.data if f["feedback_type"] == "missing"]
        
        return {
            "total_feedback": total_feedback,
            "avg_overall_rating": avg_rating,
            "avg_accuracy_rating": avg_accuracy_rating,
            "corrections_count": len(corrections),
            "false_positives_count": len(false_positives),
            "missing_count": len(missing)
        }
    
    def _generate_recommendations(
        self,
        metrics: Dict,
        errors: List[Dict],
        confidence_stats: Dict,
        feedback_stats: Dict
    ) -> List[str]:
        """Generate actionable recommendations"""
        
        recommendations = []
        
        # Accuracy recommendations
        if metrics["accuracy_rate"] < 85:
            recommendations.append(
                f"⚠️  Accuracy rate is {metrics['accuracy_rate']:.1f}% (target: 85%+). "
                "Consider reviewing Vision API prompts and adding more context."
            )
        
        if metrics["accuracy_rate"] >= 90:
            recommendations.append(
                f"✅ Excellent accuracy rate: {metrics['accuracy_rate']:.1f}%"
            )
        
        # Confidence recommendations
        high_acc = confidence_stats["high_confidence"]["accuracy"]
        medium_acc = confidence_stats["medium_confidence"]["accuracy"]
        
        if high_acc < 95:
            recommendations.append(
                f"⚠️  High confidence items have {high_acc:.1f}% accuracy (target: 95%+). "
                "May need to adjust confidence thresholds or improve detection."
            )
        
        if medium_acc < 70:
            recommendations.append(
                f"⚠️  Medium confidence items have {medium_acc:.1f}% accuracy. "
                "Consider showing more close alternatives to users."
            )
        
        # Common error patterns
        if errors:
            top_error = errors[0]
            if top_error["occurrence_count"] > 10:
                recommendations.append(
                    f"⚠️  '{top_error['detected_name']}' → '{top_error['correct_name']}' "
                    f"occurred {top_error['occurrence_count']} times. "
                    "Add this to normalization rules or prompt examples."
                )
        
        # Feedback recommendations
        if feedback_stats["avg_accuracy_rating"] > 0:
            if feedback_stats["avg_accuracy_rating"] < 3.5:
                recommendations.append(
                    f"⚠️  Users rate accuracy at {feedback_stats['avg_accuracy_rating']:.1f}/5. "
                    "Review common errors and improve detection quality."
                )
            elif feedback_stats["avg_accuracy_rating"] >= 4.0:
                recommendations.append(
                    f"✅ Good user satisfaction: {feedback_stats['avg_accuracy_rating']:.1f}/5 "
                    "accuracy rating"
                )
        
        return recommendations
    
    def _generate_prompt_improvements(self, errors: List[Dict]) -> List[str]:
        """Generate specific prompt improvement suggestions"""
        
        suggestions = []
        
        # Analyze top 10 errors for patterns
        for error in errors[:10]:
            detected = error["detected_name"]
            correct = error["correct_name"]
            count = error["occurrence_count"]
            
            suggestions.append(
                f"Add training example to Vision API prompt:\n"
                f"  ❌ Often misidentified as: '{detected}'\n"
                f"  ✅ Correct identification: '{correct}'\n"
                f"  📊 Occurrences: {count}\n"
            )
        
        return suggestions
    
    def _print_metrics(self, metrics: Dict):
        """Pretty print metrics"""
        print(f"  Total Scans: {metrics['total_scans']:,}")
        print(f"  Active Users: {metrics['active_users']:,}")
        print(f"  Total Detections: {metrics['total_detections']:,}")
        print(f"  Avg Detections/Scan: {metrics['avg_detections_per_scan']:.1f}")
        print()
        print(f"  Confirmed: {metrics['confirmed']:,} ({metrics['confirmed']/max(metrics['total_detections'], 1)*100:.1f}%)")
        print(f"  Modified: {metrics['modified']:,} ({metrics['modified']/max(metrics['total_detections'], 1)*100:.1f}%)")
        print(f"  Rejected: {metrics['rejected']:,} ({metrics['rejected']/max(metrics['total_detections'], 1)*100:.1f}%)")
        print(f"  Pending: {metrics['pending']:,}")
        print()
        print(f"  ⭐ Accuracy Rate: {metrics['accuracy_rate']:.1f}%")
        print(f"  ⭐ Avg Confidence: {metrics['avg_confidence']:.2f}")
    
    def _print_errors(self, errors: List[Dict]):
        """Pretty print common errors"""
        if not errors:
            print("  No errors recorded in this period.")
            return
        
        print(f"  Top {len(errors)} misidentifications:\n")
        for i, error in enumerate(errors, 1):
            print(f"  {i}. '{error['detected_name']}' → '{error['correct_name']}'")
            print(f"     Occurrences: {error['occurrence_count']}")
            print(f"     Last seen: {error['last_occurrence'][:10]}")
            print()
    
    def _print_confidence_stats(self, stats: Dict):
        """Pretty print confidence statistics"""
        for level, data in stats.items():
            print(f"  {level.replace('_', ' ').title()}:")
            print(f"    Count: {data['count']:,}")
            print(f"    Accuracy: {data['accuracy']:.1f}%")
            print()
    
    def _print_feedback_stats(self, stats: Dict):
        """Pretty print feedback statistics"""
        print(f"  Total Feedback Submissions: {stats['total_feedback']}")
        if stats['avg_overall_rating'] > 0:
            print(f"  Average Rating: {stats['avg_overall_rating']:.1f}/5 ⭐")
        if stats['avg_accuracy_rating'] > 0:
            print(f"  Accuracy Rating: {stats['avg_accuracy_rating']:.1f}/5")
        print()
        print(f"  Corrections: {stats['corrections_count']}")
        print(f"  False Positives: {stats['false_positives_count']}")
        print(f"  Missing Items: {stats['missing_count']}")
    
    def _print_recommendations(self, recommendations: List[str]):
        """Pretty print recommendations"""
        if not recommendations:
            print("  No specific recommendations at this time.")
            return
        
        for i, rec in enumerate(recommendations, 1):
            print(f"  {i}. {rec}\n")
    
    def _print_prompt_suggestions(self, suggestions: List[str]):
        """Pretty print prompt improvement suggestions"""
        if not suggestions:
            print("  No specific prompt improvements needed.")
            return
        
        for suggestion in suggestions[:5]:  # Show top 5
            print(f"  {suggestion}")


async def main():
    """Run optimization report"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze scanning performance")
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to analyze (default: 30)"
    )
    parser.add_argument(
        "--export",
        type=str,
        help="Export report to JSON file"
    )
    
    args = parser.parse_args()
    
    optimizer = ScanningOptimizer()
    report = await optimizer.generate_report(days=args.days)
    
    if args.export:
        with open(args.export, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\n\nReport exported to: {args.export}")
    
    print("\n" + "="*60)
    print("Report complete!")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
