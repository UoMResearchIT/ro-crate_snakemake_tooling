from dataclasses import dataclass, field
from typing import Optional

import snakemake
import os

from snakemake_interface_common.exceptions import WorkflowError  # noqa: F401
from snakemake_interface_report_plugins.reporter import ReporterBase
from snakemake_interface_report_plugins.settings import ReportSettingsBase

from rocrate.rocrate import ROCrate
from rocrate.model import ContextEntity, Person

# Optional:
# Define additional settings for your reporter.
# They will occur in the Snakemake CLI as --report-<reporter-name>-<param-name>
# Omit this class if you don't need any.
# Make sure that all defined fields are Optional (or bool) and specify a default value
# of None (or False) or anything else that makes sense in your case.
@dataclass
class ReportSettings(ReportSettingsBase):
    myparam: Optional[int] = field(
        default=None,
        metadata={
            "help": "Some help text",
            # Optionally request that setting is also available for specification
            # via an environment variable. The variable will be named automatically as
            # SNAKEMAKE_REPORT_<reporter-name>_<param-name>, all upper case.
            # This mechanism should ONLY be used for passwords and usernames.
            # For other items, we rather recommend to let people use a profile
            # for setting defaults
            # (https://snakemake.readthedocs.io/en/stable/executing/cli.html#profiles).
            "env_var": False,
            # Optionally specify a function that parses the value given by the user.
            # This is useful to create complex types from the user input.
            #"parse_func": ...,
            # If a parse_func is specified, you also have to specify an unparse_func
            # that converts the parsed value back to a string.
            #"unparse_func": ...,
            # Optionally specify that setting is required when the reporter is in use.
            "required": False,
        },
    )


# Required:
# Implementation of your reporter
class Reporter(ReporterBase):
    def __post_init__(self, excludelist = [".snakemake", ".git", ".github", ".test", ".gitignore"]):
        # initialize additional attributes
        # Do not overwrite the __init__ method as this is kept in control of the base
        # class in order to simplify the update process.
        # See https://github.com/snakemake/snakemake-interface-report-plugins/snakemake_interface_report_plugins/reporter.py # noqa: E501
        # for attributes of the base class.
        # In particular, the settings of above ReportSettings class are accessible via
        # self.settings.
        self.outdir = "ro-crate_out_copymetadata"
        self.excludelist = excludelist
        self.excludelist.append(self.outdir)
        # Load the existing Workflow RO-Crate
        self.old_crate = ROCrate(source='./')
        self.crate = ROCrate()

    def render(self):
        # Render the report, using attributes of the base class.

        # copy across files and data structure.
        # NOTE: we have to use the add_dataset and add_file commands,
        #       *not* the plain add command (as for the contextual entity),
        #       or the library will not load the files contained within
        #       the dataset directories.
        for entity in self.old_crate.data_entities:
            if 'Dataset' in entity.type:
                self.crate.add_dataset(source=entity.id, dest_path=entity.id, 
                                       properties=entity.properties())
            elif 'File' in entity.type:
                self.crate.add_file(source=entity.id, dest_path=entity.id,
                                    properties=entity.properties())
        
        # copy desired metadata from old crate
        for entity in self.old_crate.contextual_entities:
            self.crate.add(entity)


        # Provenance Crate - add snakemake version
        for entity in self.crate.contextual_entities:
            if entity.type == 'ComputerLanguage' and 'snakemake' in entity.id.lower():
                entity['version'] = snakemake.__version__.split("+")[0]
        
        # Provenance Crate - record execution of workflow as a CreateAction object
        instruments = {}
        for entity in self.crate.data_entities:
            if 'ComputationalWorkflow' in entity.type:
                instruments["@id"] = entity.id
        workflow_run_properties = {
            #"@id":"FIXME-a",
            "@type":"CreateAction",
            "name":"Snakemake workflow run (FIXME)",
            "endTime":"FIXME date",
            "instrument":instruments,
            #"subjectOf":{"@id":"FIXME creative work (workflow?)"},
            "object":["FIXME inputs"],
            "result":["FIXME outputs"]
        }
        print(workflow_run_properties)
        workflow_run = self.crate.add(
            ContextEntity(self.crate, properties=workflow_run_properties)
        )

        # Provenance Run Crate (individual step information)

        # print basic information (start/end) of each job
        for rulename, rule  in self.rules.items():
            print(f"rule: {rulename}")
            #print(rule)
            #print("rule: " + rec.rule)
            #print("starttime: " + str(rec.starttime))
            #print("endtime: " + str(rec.endtime))
            #print("ROCrate date published: " + str(self.crate.datePublished.date()))

        # Add Person running workflow (agent)
        person_properties = {
            #"@id": "FIXME-ORCID?",
            "givenName": "FIXME",
            "familyName": "FIXME",
            "affiliation": "FIXME"
        }
        agent = self.crate.add(Person(self.crate,
                                      "FIXME-ORCID?",
                                      properties=person_properties))
        workflow_run.append_to( "agent", [agent] )
        
        
        # Reference CreateAction in the root Dataset
        self.crate.root_dataset.append_to(
            "mentions" , [{"@id": workflow_run.id}]
        )
        
        # Set the conformsTo statement for the root Dataset.
        # Note that this will replace any pre-existing conformsTo information
        self.crate.root_dataset["conformsTo"] = [
                    {"@id": "https://w3id.org/ro/wfrun/process/0.1"},
                    {"@id": "https://w3id.org/ro/wfrun/workflow/0.5"},
                    {"@id": "https://w3id.org/workflowhub/workflow-ro-crate/1.0"}
                ]


        self.crate.write(self.outdir)

